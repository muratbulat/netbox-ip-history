from datetime import UTC
from pathlib import Path
from unittest import mock

from django.test import TestCase

from netbox_ip_history.choices import ImportStatusChoices
from netbox_ip_history.models import HistoricalIPEvent, ImportJob, ImportSource
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


class FingerprintScopeTests(TestCase):
    """Rows that differ only in VRF or other attributes are distinct events, not duplicates."""

    def setUp(self):
        self.source = make_source(source_timezone="UTC")

    def run_csv(self, text):
        return run_import(self.source, build_importer(self.source, text.encode(), format="csv"))[0]

    def test_same_row_in_two_vrfs_is_two_events(self):
        result = self.run_csv(
            "ip,timestamp,event_type,hostname,vrf,mac\n"
            "203.0.113.5,2025-01-01 10:00,create,web1,,00:00:5e:00:53:01\n"
            "203.0.113.5,2025-01-01 10:00,create,web1,VRF-B,00:00:5e:00:53:01\n"
        )
        self.assertEqual((result.created, result.duplicates), (2, 0))

    def test_rows_differing_only_in_attributes_are_distinct(self):
        base = "203.0.113.6,2025-01-01 10:00,create,web1"
        result = self.run_csv(
            "ip,timestamp,event_type,hostname,vrf_rd,mac,status,dns_name\n"
            f"{base},,,,\n"
            f"{base},65000:1,,,\n"
            f"{base},,00:00:5e:00:53:02,,\n"
            f"{base},,,active,\n"
            f"{base},,,,web1.example.com\n"
        )
        self.assertEqual((result.created, result.duplicates), (5, 0))


class SnapshotIdempotencyTests(TestCase):
    """Re-importing the same snapshot file must not create new events."""

    def setUp(self):
        self.source = make_source(source_timezone="UTC")

    def run_bytes(self, source, data, **kwargs):
        return run_import(source, build_importer(source, data), data=data, **kwargs)

    def test_reimporting_undated_rows_creates_nothing(self):
        data = (
            b"ip,timestamp,event_type,hostname\n"
            b"203.0.113.10,2025-01-01 10:00,create,web1\n"
            b"203.0.113.11,,create,web2\n"
        )
        first, _ = self.run_bytes(self.source, data)
        second, _ = self.run_bytes(self.source, data)
        self.assertEqual(first.created, 2)
        self.assertEqual((second.created, second.duplicates), (0, 2))

    def test_reimporting_infoblox_export_creates_nothing(self):
        source = make_source("nios", "infoblox")
        data = (FIXTURES / "infoblox_nios.csv").read_bytes()
        self.assertEqual(self.run_bytes(source, data)[0].created, 5)
        shifted = b"\n" + data  # same records on different line numbers
        self.assertEqual(self.run_bytes(source, shifted)[0].created, 0)

    def test_infoblox_record_ids_do_not_depend_on_line_numbers(self):
        source = make_source("nios", "infoblox")
        self.run_bytes(source, (FIXTURES / "infoblox_nios.csv").read_bytes())
        ids = set(HistoricalIPEvent.objects.filter(source=source).values_list("source_record_id", flat=True))
        self.assertIn("hostrecord:192.0.2.40:device-01.example.com", ids)
        self.assertIn("fixedaddress:192.0.2.42:device-02.example.com", ids)

    def test_reimporting_the_same_file_warns(self):
        data = b"ip,timestamp,event_type\n203.0.113.12,2025-01-01 10:00,create\n"
        _, first_job = self.run_bytes(self.source, data)
        self.assertEqual(first_job.summary.get("warnings", []), [])
        result, job = self.run_bytes(self.source, data)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn(f"#{first_job.pk}", result.warnings[0])
        self.assertEqual(job.summary["warnings"], result.warnings)
        dry, _ = self.run_bytes(self.source, data, dry_run=True)
        self.assertEqual(len(dry.warnings), 1)
        other = make_source("other-source", source_timezone="UTC")
        self.assertEqual(self.run_bytes(other, data)[0].warnings, [])


class PrefixLengthTests(TestCase):
    def setUp(self):
        self.source = make_source(source_timezone="UTC")

    def prefix(self, ip, value):
        from netbox_ip_history.services.import_service import normalize_record

        record = {"ip_address": ip, "timestamp": "2025-01-01T00:00:00+00:00", "prefix_length": value}
        return normalize_record(self.source, record)["prefix_length"]

    def test_prefix_length_is_clamped_by_address_family(self):
        self.assertEqual(self.prefix("192.0.2.1", "24"), 24)
        self.assertEqual(self.prefix("192.0.2.1", "32"), 32)
        self.assertIsNone(self.prefix("192.0.2.1", "64"))
        self.assertEqual(self.prefix("192.0.2.1/26", "64"), 26)  # falls back to the address's own prefix
        self.assertEqual(self.prefix("2001:db8::1", "64"), 64)
        self.assertIsNone(self.prefix("2001:db8::1", "129"))

    def test_dotted_netmasks_are_accepted(self):
        self.assertEqual(self.prefix("192.0.2.1", "255.255.255.0"), 24)
        self.assertEqual(self.prefix("192.0.2.1", "255.255.255.252"), 30)
        self.assertIsNone(self.prefix("192.0.2.1", "255.0.255.0"))  # not contiguous
        self.assertIsNone(self.prefix("2001:db8::1", "255.255.255.0"))

    def test_zero_length_prefix_is_kept(self):
        self.assertEqual(self.prefix("192.0.2.1/24", "0"), 0)


class DateOrderTests(TestCase):
    def parse(self, value, **source_fields):
        from netbox_ip_history.services.import_service import normalize_record

        source = make_source(f"src-{ImportSource.objects.count()}", source_timezone="UTC", **source_fields)
        return normalize_record(source, {"ip_address": "192.0.2.1", "timestamp": value})["timestamp"]

    def test_day_first_is_the_default(self):
        self.assertEqual((self.parse("03/04/2025").month, self.parse("03/04/2025").day), (4, 3))

    def test_month_first_sources(self):
        parsed = self.parse("03/04/2025 10:00", date_order="mdy").astimezone(UTC)
        self.assertEqual((parsed.month, parsed.day, parsed.hour), (3, 4, 10))
        unambiguous = self.parse("13/04/2025", date_order="mdy")  # no 13th month: still day-first
        self.assertEqual((unambiguous.month, unambiguous.day), (4, 13))
        dotted = self.parse("03.04.2025", date_order="mdy")  # dotted dates are always day-first
        self.assertEqual((dotted.month, dotted.day), (4, 3))
