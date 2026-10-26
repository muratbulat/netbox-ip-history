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
