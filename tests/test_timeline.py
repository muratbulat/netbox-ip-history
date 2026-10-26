from datetime import UTC, datetime

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from netbox_ip_history.choices import EventTypeChoices as E
from netbox_ip_history.models import HistoricalIPEvent, ImportJob
from netbox_ip_history.services.timeline import (
    ObjectLookup,
    change_details,
    classify_event_type,
    compare_sources,
    extract_ip_from_change,
    get_timeline,
    native_events,
    owner_type,
    resolve_assigned_object_type,
)

from .helpers import ip_change, make_device, make_interface, make_source, make_vm_interface

DEVICE_PAYLOAD = {"assigned_object": {"name": "eth0", "device": {"name": "device-01"}}}
VM_PAYLOAD = {"assigned_object": {"name": "eth0", "virtual_machine": {"name": "vm-01"}}}


class ClassificationTests(SimpleTestCase):
    def classify(self, pre, post, **kwargs):
        return classify_event_type(
            "update", "admin", pre_payload=pre, post_payload=post,
            pre_details=change_details(pre), post_details=change_details(post), **kwargs,
        )

    def test_create_delete(self):
        self.assertEqual(classify_event_type("create", "admin"), E.CREATED)
        self.assertEqual(classify_event_type("create", "ping-scanner"), E.DISCOVERED)
        self.assertEqual(classify_event_type("delete"), E.DELETED)
        self.assertIsNone(classify_event_type("frobnicate"))

    def test_assignment_transitions(self):
        self.assertEqual(self.classify({}, DEVICE_PAYLOAD), E.ASSIGNED)
        self.assertEqual(self.classify(DEVICE_PAYLOAD, {}), E.UNASSIGNED)
        other_device = {"assigned_object": {"name": "eth0", "device": {"name": "device-02"}}}
        self.assertEqual(self.classify(DEVICE_PAYLOAD, other_device), E.REASSIGNED)
        self.assertEqual(self.classify(DEVICE_PAYLOAD, VM_PAYLOAD), E.OWNER_CHANGED)
        other_iface = {"assigned_object": {"name": "eth1", "device": {"name": "device-01"}}}
        self.assertEqual(self.classify(DEVICE_PAYLOAD, other_iface), E.INTERFACE_CHANGED)

    def test_attribute_changes(self):
        self.assertEqual(self.classify({"dns_name": "a.example.com"}, {"dns_name": "b.example.com"}), E.DNS_CHANGED)
        # A bare "hostname" key names the owner host, so changing it is a reassignment.
        self.assertEqual(self.classify({"hostname": "a"}, {"hostname": "b"}), E.REASSIGNED)
        self.assertEqual(self.classify({"description": "a"}, {"description": "b"}), E.UPDATED)

    def test_status_change_has_priority(self):
        result = self.classify(DEVICE_PAYLOAD, VM_PAYLOAD, pre_status="active", post_status="deprecated")
        self.assertEqual(result, E.STATUS_CHANGED)

    def test_details_from_string_and_nested_payloads(self):
        self.assertEqual(change_details({"assigned_object": "device-01 > eth0"})["host_name"], "device-01")
        self.assertEqual(change_details({"assigned_object": "eth0"})["host_name"], "")
        self.assertEqual(change_details(VM_PAYLOAD)["host_name"], "vm-01")
        self.assertEqual(change_details({"vrf": {"name": "BLUE"}})["vrf_name"], "BLUE")
        self.assertEqual(change_details({"vrf": None})["vrf_name"], "")

    def test_assigned_object_type_shapes(self):
        self.assertEqual(resolve_assigned_object_type({"assigned_object_type": "dcim.interface"}), "interface")
        self.assertEqual(
            resolve_assigned_object_type({"assigned_object_type": "virtualization.vminterface"}), "vminterface"
        )
        self.assertEqual(
            resolve_assigned_object_type({"assigned_object": {"url": "/api/virtualization/interfaces/5/"}}),
            "vminterface",
        )
        self.assertEqual(owner_type(DEVICE_PAYLOAD), "device")
        self.assertEqual(owner_type({"assigned_object": "device-01 > eth0"}), "")

    def test_extract_ip_is_exact_and_canonical(self):
        change = {"postchange_data": {"address": "2001:0db8::0008/64"}, "object_repr": "ignored"}
        self.assertEqual(extract_ip_from_change(change), ("2001:db8::8", 64))
        self.assertEqual(extract_ip_from_change({"object_repr": "198.51.100.80/24"}), ("198.51.100.80", 24))
        self.assertEqual(extract_ip_from_change({"object_repr": "garbage"}), (None, None))


class ObjectLookupTests(TestCase):
    def test_integer_payloads_resolve_with_type_disambiguation(self):
        from django.contrib.contenttypes.models import ContentType
        from virtualization.models import VMInterface

        iface = make_interface(make_device("device-01"), "eth0")
        vm_iface = make_vm_interface("vm-01", "eth0")
        dcim_ct = ContentType.objects.get_for_model(iface).pk
        vm_ct = ContentType.objects.get_for_model(VMInterface).pk
        payloads = [
            {"assigned_object_id": iface.pk, "assigned_object_type": dcim_ct},
            {"assigned_object_id": vm_iface.pk, "assigned_object_type": vm_ct},
        ]
        lookup = ObjectLookup(payloads)
        self.assertEqual(change_details(payloads[0], lookup)["host_name"], "device-01")
        self.assertEqual(change_details(payloads[1], lookup)["host_name"], "vm-01")
        self.assertEqual(owner_type(payloads[1], lookup), "virtualmachine")

    def test_dns_name_of_known_device_wins_over_vm(self):
        make_device("device-01.example.com")
        make_vm_interface("vm-01")
        payload = {"dns_name": "device-01.example.com", "virtual_machine": {"name": "vm-01"}}
        self.assertEqual(change_details(payload, ObjectLookup([payload]))["host_name"], "device-01.example.com")

    def test_deleted_interface_falls_back_to_its_changelog(self):
        iface = make_interface(make_device("device-01"), "eth7")
        from core.models import ObjectChange
        from django.contrib.contenttypes.models import ContentType

        ObjectChange.objects.create(
            changed_object_type=ContentType.objects.get_for_model(iface),
            changed_object_id=iface.pk,
            action="delete",
            object_repr="device-01 > eth7",
            user_name="admin",
            request_id="00000000-0000-0000-0000-000000000001",
        )
        pk = iface.pk
        iface.delete()
        payload = {"assigned_object_id": pk, "assigned_object_type": "dcim.interface"}
        details = change_details(payload, ObjectLookup([payload]))
        self.assertEqual((details["host_name"], details["interface_name"]), ("device-01", "eth7"))


class TimelineTests(TestCase):
    def setUp(self):
        self.csv = make_source()
        self.job = ImportJob.objects.create(source=self.csv, status="completed")

    def event(self, ip, minutes=0, **kwargs):
        defaults = {"event_type": E.IMPORTED, "source": self.csv, "import_job": self.job}
        return HistoricalIPEvent.objects.create(
            ip_address=ip,
            timestamp=datetime(2026, 2, 1, 0, minutes, tzinfo=UTC),
            fingerprint=f"{ip}-{minutes}-{kwargs.get('vrf_name', '')}",
            **{**defaults, **kwargs},
        )

    def test_global_vrf_matches_native_and_imported_spellings(self):
        ip_change("192.0.2.1/24", minutes=1)  # native event, stored with empty VRF
        self.event("192.0.2.1", minutes=2, vrf_name="Global")  # legacy spelling
        self.event("192.0.2.1", minutes=3)
        self.event("192.0.2.1", minutes=4, vrf_name="BLUE")
        self.assertEqual(len(get_timeline("192.0.2.1", vrf="Global")), 3)
        self.assertEqual(len(get_timeline("192.0.2.1", vrf="global")), 3)
        self.assertEqual([e["vrf"] for e in get_timeline("192.0.2.1", vrf="BLUE")], ["BLUE"])
        self.assertEqual(len(get_timeline("192.0.2.1")), 4)

    def test_ipv6_query_is_canonicalized(self):
        self.event("2001:db8::1")
        self.assertEqual(len(get_timeline("2001:0DB8:0000::0001/64")), 1)

    def test_invalid_ip_returns_empty_without_querying(self):
        with self.assertNumQueries(0):
            self.assertEqual(get_timeline("192.0.2.300"), [])
            self.assertEqual(get_timeline("not-an-ip"), [])
            self.assertEqual(native_events("not-an-ip"), [])

    def test_native_events_match_exact_address_only(self):
        for minutes, address in enumerate(("198.51.100.8/24", "198.51.100.80/24", "198.51.100.85/24")):
            ip_change(address, minutes=minutes)
        HistoricalIPEvent.objects.all().delete()  # simulate history from before the plugin
        events = get_timeline("198.51.100.8")
        self.assertEqual([e["ip_address"] for e in events], ["198.51.100.8"])
        self.assertTrue(events[0]["native"])

    def test_recorded_changes_are_not_duplicated(self):
        ip_change("192.0.2.2/24", minutes=1)
        ip_change("192.0.2.2/24", action="update", pre={"address": "192.0.2.2/24"},
                  post={"address": "192.0.2.2/24", "dns_name": "device-01.example.com"}, minutes=2)
        HistoricalIPEvent.objects.filter(source_record_id__isnull=False).order_by("timestamp").first().delete()
        events = get_timeline("192.0.2.2", oldest_first=True)
        self.assertEqual([e["event_type"] for e in events], [E.CREATED, E.DNS_CHANGED])

    def test_query_count_is_constant(self):
        device = make_device("device-01")
        interfaces = [make_interface(device, f"eth{i}") for i in range(12)]

        def build(ip, count):
            for i in range(count):
                payload = {"address": f"{ip}/24", "assigned_object_id": interfaces[i].pk,
                           "assigned_object_type": "dcim.interface", "vrf": None}
                ip_change(f"{ip}/24", action="update", pre={"address": f"{ip}/24"}, post=payload, minutes=i)

        build("192.0.2.3", 2)
        build("192.0.2.4", 12)
        HistoricalIPEvent.objects.filter(ip_address="192.0.2.4").delete()  # force live native path too

        def queries(ip):
            with CaptureQueriesContext(connection) as ctx:
                events = get_timeline(ip)
            return len(ctx.captured_queries), events

        small, _ = queries("192.0.2.3")
        large, events = queries("192.0.2.4")
        self.assertEqual(len(events), 12)
        self.assertEqual(events[0]["owner_name"], "device-01")
        self.assertLessEqual(large, small + 6)  # bounded by lookup tables, not by event count
        self.assertLess(large, 15)

    def test_compare_sources_latest_per_source(self):
        ip_change("192.0.2.5/24", post={"address": "192.0.2.5/24", "dns_name": "device-01.example.com"})
        self.event("192.0.2.5", minutes=1, hostname="device-02.example.com")
        self.event("192.0.2.5", minutes=5, hostname="device-03.example.com")
        rows = compare_sources("192.0.2.5")
        self.assertEqual([r["source"] for r in rows], ["NetBox", self.csv.name])
        self.assertEqual(rows[1]["hostname"], "device-03.example.com")
