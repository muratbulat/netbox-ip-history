import uuid

from core.models import ObjectChange
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from ipam.models import VRF, IPAddress
from netbox.context_managers import event_tracking

from netbox_ip_history.choices import EventTypeChoices, SourceTypeChoices
from netbox_ip_history.models import HistoricalIPEvent, ImportSource

from .helpers import ip_change, make_device, make_interface


class NativeTrackingTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.id = uuid.uuid4()
        self.request.user = get_user_model().objects.create_user(username="operator")

    def tracked(self, fn):
        with event_tracking(self.request):
            return fn()

    def test_ip_lifecycle_is_recorded(self):
        iface = make_interface(make_device("device-01"))
        ip = self.tracked(lambda: IPAddress.objects.create(address="192.0.2.50/24", dns_name="device-01.example.com"))

        def assign():
            ip.snapshot()
            ip.assigned_object = iface
            ip.save()

        self.tracked(assign)
        self.tracked(ip.delete)

        events = list(HistoricalIPEvent.objects.filter(ip_address="192.0.2.50").order_by("timestamp", "pk"))
        self.assertEqual(
            [e.event_type for e in events],
            [EventTypeChoices.CREATED, EventTypeChoices.ASSIGNED, EventTypeChoices.DELETED],
        )
        self.assertEqual(events[1].owner_name, "device-01")
        self.assertEqual(events[1].interface_name, "eth0")
        self.assertEqual(events[0].source_username, "operator")
        self.assertTrue(all(e.vrf_name == "" for e in events))
        self.assertIsNone(events[0].import_job)
        self.assertIsNone(events[2].related_netbox_ip)
        self.assertEqual(events[0].source.source_type, SourceTypeChoices.NETBOX)

    def test_vrf_name_is_recorded(self):
        vrf = VRF.objects.create(name="BLUE")
        self.tracked(lambda: IPAddress.objects.create(address="198.51.100.50/24", vrf=vrf))
        self.assertEqual(HistoricalIPEvent.objects.get(ip_address="198.51.100.50").vrf_name, "BLUE")

    def test_recording_does_not_create_changelog_entries(self):
        self.tracked(lambda: IPAddress.objects.create(address="192.0.2.51/24"))
        self.assertTrue(HistoricalIPEvent.objects.filter(ip_address="192.0.2.51").exists())
        self.assertFalse(ObjectChange.objects.filter(changed_object_type__model="historicalipevent").exists())

    def test_recording_is_idempotent(self):
        change = ip_change("192.0.2.52/24")
        change.save()
        self.assertEqual(HistoricalIPEvent.objects.filter(fingerprint=f"netbox-oc-{change.pk}").count(), 1)

    def test_deleted_native_source_is_recreated(self):
        ip_change("192.0.2.53/24")
        HistoricalIPEvent.objects.all().delete()
        ImportSource.objects.filter(slug="netbox").delete()
        ip_change("192.0.2.54/24")
        self.assertTrue(HistoricalIPEvent.objects.filter(ip_address="192.0.2.54").exists())
        self.assertEqual(ImportSource.objects.filter(slug="netbox").count(), 1)

    @override_settings(PLUGINS_CONFIG={"netbox_ip_history": {"enable_native_event_tracking": False}})
    def test_tracking_can_be_disabled(self):
        self.tracked(lambda: IPAddress.objects.create(address="192.0.2.55/24"))
        self.assertFalse(HistoricalIPEvent.objects.filter(ip_address="192.0.2.55").exists())

    def test_other_models_are_ignored(self):
        self.tracked(lambda: make_device("device-09"))
        self.assertFalse(HistoricalIPEvent.objects.exists())


class BackfillOnMigrateTests(TestCase):
    def setUp(self):
        from django.apps import apps

        self.app_config = apps.get_app_config("netbox_ip_history")
        self.apps = apps

    def migrate_signal(self, **kwargs):
        from django.db.models.signals import post_migrate

        with self.captureOnCommitCallbacks(execute=True):
            post_migrate.send(sender=self.app_config, app_config=self.app_config, using="default",
                              apps=self.apps, verbosity=0, interactive=False, plan=[], **kwargs)

    def test_unrecorded_changes_are_recorded_and_searchable(self):
        from extras.models import CachedValue

        ip_change("192.0.2.90/24")
        ip_change("192.0.2.91/24", minutes=1)
        HistoricalIPEvent.objects.all().delete()  # history from before the plugin was installed
        CachedValue.objects.all().delete()

        self.migrate_signal()

        events = HistoricalIPEvent.objects.filter(source__slug="netbox")
        self.assertEqual(set(events.values_list("ip_address", flat=True)), {"192.0.2.90", "192.0.2.91"})
        cached = CachedValue.objects.filter(object_type__model="historicalipevent", field="ip_address")
        self.assertEqual(set(cached.values_list("value", flat=True)), {"192.0.2.90", "192.0.2.91"})

    def test_recorded_changes_are_not_rewritten(self):
        from netbox_ip_history.signals import backfill_native_events

        ip_change("192.0.2.92/24")
        before = HistoricalIPEvent.objects.get().last_updated
        self.assertEqual(backfill_native_events(), 0)
        self.assertEqual(HistoricalIPEvent.objects.get().last_updated, before)

    def test_batches_cover_every_change(self):
        from netbox_ip_history.signals import backfill_native_events

        for i in range(5):
            ip_change(f"192.0.2.{100 + i}/24", minutes=i)
        HistoricalIPEvent.objects.all().delete()
        self.assertEqual(backfill_native_events(batch_size=2), 5)

    @override_settings(PLUGINS_CONFIG={"netbox_ip_history": {
        "enable_native_event_tracking": True, "backfill_on_migrate": False,
    }})
    def test_backfill_can_be_disabled(self):
        ip_change("192.0.2.93/24")
        HistoricalIPEvent.objects.all().delete()
        self.migrate_signal()
        self.assertFalse(HistoricalIPEvent.objects.exists())

    def test_skipped_for_other_apps_and_missing_tables(self):
        from netbox_ip_history.signals import backfill_after_migrate

        ip_change("192.0.2.94/24")
        HistoricalIPEvent.objects.all().delete()
        backfill_after_migrate(sender=self.apps.get_app_config("ipam"), using="default", apps=self.apps)

        class StateWithoutPlugin:
            def get_model(self, app_label, model_name):
                raise LookupError(model_name)

        backfill_after_migrate(sender=self.app_config, using="default", apps=StateWithoutPlugin())
        backfill_after_migrate(sender=self.app_config, using="other", apps=self.apps)
        self.assertFalse(HistoricalIPEvent.objects.exists())
