import importlib
from datetime import UTC, datetime

from django.apps import apps
from django.test import TestCase

from netbox_ip_history.models import HistoricalIPEvent, ImportJob
from netbox_ip_history.services.import_service import build_importer, run_import
from netbox_ip_history.services.normalize import FINGERPRINT_FIELDS, fingerprint

from .helpers import ip_change, make_source

fingerprints = importlib.import_module("netbox_ip_history.migrations._fingerprints")


def live_fingerprint(event):
    return fingerprint(event.source.slug, {f: getattr(event, f) for f in FINGERPRINT_FIELDS})


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

    def test_v2_recompute_matches_live_algorithm_and_dedupes(self):
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
            self.assertEqual(event.fingerprint, live_fingerprint(event))
        native_after = HistoricalIPEvent.objects.get(pk=native.pk)
        self.assertEqual(native_after.fingerprint, native.fingerprint)

    def test_reimport_after_recompute_creates_nothing(self):
        data = b"ip,timestamp,event_type,hostname\n203.0.113.8,2025-01-01 10:00,create,web1\n"
        _, job = run_import(self.source, build_importer(self.source, data))
        HistoricalIPEvent.objects.filter(import_job=job).update(fingerprint="pre-upgrade")

        fingerprints.recompute(apps, fingerprints.fingerprint_v2)
        result, _ = run_import(self.source, build_importer(self.source, data))

        self.assertEqual((result.created, result.duplicates), (0, 1))
