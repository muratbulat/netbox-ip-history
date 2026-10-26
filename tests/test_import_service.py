from pathlib import Path
from unittest import mock

from django.test import TestCase

from netbox_ip_history.choices import ImportStatusChoices
from netbox_ip_history.models import HistoricalIPEvent, ImportJob
from netbox_ip_history.services import import_service
from netbox_ip_history.services.import_service import build_importer, rollback_job, run_import

from .helpers import make_source

FIXTURES = Path(__file__).parent / "fixtures"


class ImportServiceTests(TestCase):
    def setUp(self):
        self.source = make_source(source_timezone="UTC")
        self.data = (FIXTURES / "generic_history.csv").read_bytes()

    def importer(self, data=None):
        return build_importer(self.source, data or self.data, format="csv")

    def test_dry_run_persists_nothing(self):
        result, job = run_import(self.source, self.importer(), dry_run=True)
        self.assertIsNone(job)
        self.assertEqual((result.total, result.created, result.duplicates, result.error_count), (6, 3, 1, 2))
        self.assertEqual(len(result.preview), 3)
        self.assertFalse(ImportJob.objects.exists())
        self.assertFalse(HistoricalIPEvent.objects.exists())

    def test_live_import_creates_job_and_events(self):
        result, job = run_import(self.source, self.importer(), filename="history.csv", data=self.data)
        job.refresh_from_db()
        self.assertEqual(job.status, ImportStatusChoices.COMPLETED)
        self.assertEqual((job.total_records, job.created_records, job.duplicate_records, job.error_records),
                         (6, 3, 1, 2))
        self.assertEqual(len(job.file_hash), 64)
        events = HistoricalIPEvent.objects.filter(import_job=job)
        self.assertEqual(events.count(), 3)
        self.assertEqual(set(events.values_list("vrf_name", flat=True)), {"", "BLUE"})
        self.assertEqual({e["row"] for e in job.error_details}, {5, 6})

    def test_reimport_is_fully_deduplicated(self):
        run_import(self.source, self.importer())
        result, _ = run_import(self.source, self.importer())
        self.assertEqual((result.created, result.duplicates), (0, 4))
        self.assertEqual(HistoricalIPEvent.objects.count(), 3)

    def test_events_are_inserted_in_batches(self):
        rows = "".join(f"2026-01-01T00:{i:02d}:00+00:00,192.0.2.{i},created\n" for i in range(1, 8))
        data = f"timestamp,ip,event_type\n{rows}".encode()
        original = HistoricalIPEvent.objects.bulk_create
        with (
            mock.patch.object(import_service, "BATCH_SIZE", 3),
            mock.patch.object(HistoricalIPEvent.objects, "bulk_create", side_effect=original) as bulk_create,
        ):
            result, _ = run_import(self.source, self.importer(data))
        self.assertEqual(result.created, 7)
        self.assertEqual([len(call.args[0]) for call in bulk_create.call_args_list], [3, 3, 1])

    def test_failure_rolls_back_events_and_keeps_failed_job(self):
        with (
            mock.patch.object(HistoricalIPEvent.objects, "bulk_create", side_effect=RuntimeError("boom")),
            self.assertRaises(RuntimeError),
        ):
            run_import(self.source, self.importer())
        self.assertFalse(HistoricalIPEvent.objects.exists())
        job = ImportJob.objects.get()
        self.assertEqual(job.status, ImportStatusChoices.FAILED)
        self.assertIn("boom", job.error_details[-1]["error"])

    def test_rollback(self):
        _, job = run_import(self.source, self.importer())
        self.assertEqual(rollback_job(job), 3)
        job.refresh_from_db()
        self.assertEqual(job.status, ImportStatusChoices.ROLLED_BACK)
        self.assertEqual(job.summary["rolled_back_events"], 3)
        self.assertFalse(HistoricalIPEvent.objects.exists())

    def test_snapshot_rows_share_one_timestamp(self):
        source = make_source("infoblox", "infoblox")
        data = (FIXTURES / "infoblox_nios.csv").read_bytes()
        result, _ = run_import(source, build_importer(source, data))
        self.assertEqual(result.created, 5)
        self.assertEqual(HistoricalIPEvent.objects.values("timestamp").distinct().count(), 1)

    def test_long_values_are_truncated(self):
        data = f"ip,hostname\n192.0.2.9,{'x' * 400}\n".encode()
        run_import(self.source, self.importer(data))
        self.assertEqual(len(HistoricalIPEvent.objects.get().hostname), 255)
