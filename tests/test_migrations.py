import importlib
from datetime import UTC, datetime
from pathlib import Path

from django.apps import apps
from django.test import TestCase

from netbox_ip_history.models import HistoricalIPEvent, ImportJob
from netbox_ip_history.services.import_service import build_importer, run_import
from netbox_ip_history.services.normalize import FINGERPRINT_FIELDS, fingerprint

from .helpers import ip_change, make_source

fingerprints = importlib.import_module("netbox_ip_history.migrations._fingerprints")
migration_0010 = importlib.import_module("netbox_ip_history.migrations.0010_snapshot_fingerprint_v3")
FIXTURES = Path(__file__).parent / "fixtures"


def live_fingerprint(event):
    return fingerprint(
        event.source.slug, {**{f: getattr(event, f) for f in FINGERPRINT_FIELDS}, "snapshot": event.snapshot}
    )


class FingerprintMigrationTests(TestCase):
    def setUp(self):
        self.source = make_source(source_timezone="UTC")
        self.job = ImportJob.objects.create(source=self.source, status="completed")

    def legacy_event(self, fingerprint, **fields):
        defaults = {
            "ip_address": "203.0.113.7",
            "timestamp": datetime(2025, 1, 1, 10, 0, tzinfo=UTC),
            "event_type": "created",
            "hostname": "web1",
        }
        return HistoricalIPEvent.objects.create(
            source=self.source, import_job=self.job, fingerprint=fingerprint, **{**defaults, **fields}
        )

    def test_latest_frozen_algorithm_matches_live(self):
        event = self.legacy_event("x", vrf_name="VRF-B", mac_address="00:00:5e:00:53:07", snapshot=True)
        self.assertEqual(fingerprints.fingerprint_v3(self.source.slug, event), live_fingerprint(event))

    def test_v2_recompute_dedupes_and_skips_native(self):
        keeper = self.legacy_event("legacy-1")
        self.legacy_event("legacy-2")  # same fields, different legacy hash: a duplicate all along
        other_vrf = self.legacy_event("legacy-3", vrf_name="VRF-B")
        ip_change("203.0.113.7/24")
        native = HistoricalIPEvent.objects.get(fingerprint__startswith="netbox-oc-")

        changed, removed = fingerprints.recompute(apps, fingerprints.fingerprint_v2)

        self.assertEqual((changed, removed), (2, 1))
        self.assertEqual(
            set(HistoricalIPEvent.objects.values_list("pk", flat=True)), {keeper.pk, other_vrf.pk, native.pk}
        )
        for event in HistoricalIPEvent.objects.filter(pk__in=(keeper.pk, other_vrf.pk)):
            self.assertEqual(event.fingerprint, fingerprints.fingerprint_v2(self.source.slug, event))
        native_after = HistoricalIPEvent.objects.get(pk=native.pk)
        self.assertEqual(native_after.fingerprint, native.fingerprint)

    def test_0010_flags_snapshots_and_makes_reimport_idempotent(self):
        data = (
            b"ip,timestamp,event_type,hostname\n"
            b"203.0.113.8,2025-01-01 10:00,create,web1\n"
            b"203.0.113.9,,create,web2\n"
        )
        _, job = run_import(self.source, build_importer(self.source, data))
        # State left by 1.0.0: no snapshot flag and fingerprints from an older algorithm.
        for event in HistoricalIPEvent.objects.filter(import_job=job):
            HistoricalIPEvent.objects.filter(pk=event.pk).update(snapshot=False, fingerprint=f"pre-upgrade-{event.pk}")

        migration_0010.forwards(apps, None)

        flags = dict(HistoricalIPEvent.objects.filter(import_job=job).values_list("ip_address", "snapshot"))
        self.assertEqual(flags, {"203.0.113.8": False, "203.0.113.9": True})
        result, _ = run_import(self.source, build_importer(self.source, data))
        self.assertEqual((result.created, result.duplicates), (0, 2))

    def test_0010_rewrites_infoblox_record_ids(self):
        source = make_source("nios", "infoblox")
        data = (FIXTURES / "infoblox_nios.csv").read_bytes()
        _, job = run_import(source, build_importer(source, data))
        for i, event in enumerate(HistoricalIPEvent.objects.filter(import_job=job)):
            HistoricalIPEvent.objects.filter(pk=event.pk).update(
                source_record_id=f"{event.source_event_type}:{i + 2}:0", snapshot=False, fingerprint=f"old-{i}"
            )

        migration_0010.forwards(apps, None)

        ids = set(HistoricalIPEvent.objects.filter(import_job=job).values_list("source_record_id", flat=True))
        self.assertIn("hostrecord:192.0.2.40:device-01.example.com", ids)
        self.assertTrue(all(HistoricalIPEvent.objects.filter(import_job=job).values_list("snapshot", flat=True)))
        self.assertEqual(run_import(source, build_importer(source, b"\n" + data))[0].created, 0)
