from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase, mock

from netbox_ip_history.choices import EventType
from netbox_ip_history.services.timeline import (
    _guess_owner_type,
    classify_event_type,
    extract_netbox_change_details,
    native_events,
)


def _classify(action, pre_payload, post_payload, user_str="admin", pre_status=None, post_status=None):
    """Mirror how signals.py / native_events() / NativeEventWrapper call classify_event_type:
    extract details from each side's payload, then diff."""
    pre_details = extract_netbox_change_details(pre_payload) if action == "update" and pre_payload else {}
    post_details = extract_netbox_change_details(post_payload) if action == "update" and post_payload else {}
    return classify_event_type(
        action, user_str,
        pre_payload=pre_payload, post_payload=post_payload,
        pre_details=pre_details, post_details=post_details,
        pre_status=pre_status, post_status=post_status,
    )


class LifecycleEventClassificationTests(TestCase):
    def test_create_is_created_or_discovered(self):
        self.assertEqual(_classify("create", {}, {"address": "10.0.0.1/24"}, user_str="admin"), EventType.CREATED)
        self.assertEqual(_classify("create", {}, {"address": "10.0.0.1/24"}, user_str="netbox-ping"), EventType.DISCOVERED)

    def test_delete_is_deleted(self):
        self.assertEqual(_classify("delete", {"address": "10.0.0.1/24"}, {}), EventType.DELETED)

    def test_deletion_and_recreation_are_distinct_events(self):
        """IP deleted, then a later, unrelated ObjectChange recreates it: each
        change is classified independently by its own action."""
        deleted = _classify("delete", {"address": "10.0.0.5/24", "assigned_object": {"device": {"name": "srv01"}}}, {})
        recreated = _classify("create", {}, {"address": "10.0.0.5/24"})
        self.assertEqual(deleted, EventType.DELETED)
        self.assertEqual(recreated, EventType.CREATED)

    def test_assigned_to_device_interface(self):
        pre = {"address": "10.0.0.1/24"}
        post = {"address": "10.0.0.1/24", "assigned_object": {"name": "eth0", "device": {"name": "srv01"}}}
        self.assertEqual(_classify("update", pre, post), EventType.ASSIGNED)

    def test_assigned_to_vm_interface(self):
        pre = {"address": "10.0.0.1/24"}
        post = {"address": "10.0.0.1/24", "assigned_object": {"name": "eth0", "virtual_machine": {"name": "vm01"}}}
        self.assertEqual(_classify("update", pre, post), EventType.ASSIGNED)

    def test_unassigned(self):
        pre = {"address": "10.0.0.1/24", "assigned_object": {"name": "eth0", "device": {"name": "srv01"}}}
        post = {"address": "10.0.0.1/24"}
        self.assertEqual(_classify("update", pre, post), EventType.UNASSIGNED)

    def test_reassigned_device_to_device(self):
        pre = {"assigned_object": {"name": "eth0", "device": {"name": "srv01"}}}
        post = {"assigned_object": {"name": "eth0", "device": {"name": "srv02"}}}
        self.assertEqual(_classify("update", pre, post), EventType.REASSIGNED)

    def test_reassigned_vm_to_vm(self):
        pre = {"assigned_object": {"name": "eth0", "virtual_machine": {"name": "vm01"}}}
        post = {"assigned_object": {"name": "eth0", "virtual_machine": {"name": "vm02"}}}
        self.assertEqual(_classify("update", pre, post), EventType.REASSIGNED)

    def test_owner_changed_device_to_vm(self):
        pre = {"assigned_object": {"name": "eth0", "device": {"name": "srv01"}}}
        post = {"assigned_object": {"name": "eth0", "virtual_machine": {"name": "vm01"}}}
        self.assertEqual(_classify("update", pre, post), EventType.OWNER_CHANGED)

    def test_owner_changed_vm_to_device(self):
        pre = {"assigned_object": {"name": "eth0", "virtual_machine": {"name": "vm01"}}}
        post = {"assigned_object": {"name": "eth0", "device": {"name": "srv01"}}}
        self.assertEqual(_classify("update", pre, post), EventType.OWNER_CHANGED)

    def test_interface_changed_same_device(self):
        pre = {"assigned_object": {"name": "eth0", "device": {"name": "srv01"}}}
        post = {"assigned_object": {"name": "eth1", "device": {"name": "srv01"}}}
        self.assertEqual(_classify("update", pre, post), EventType.INTERFACE_CHANGED)

    def test_dns_changed_with_no_assignment_change(self):
        pre = {"dns_name": "old.example.com"}
        post = {"dns_name": "new.example.com"}
        self.assertEqual(_classify("update", pre, post), EventType.DNS_CHANGED)

    def test_hostname_changed_with_no_dns_or_assignment_change(self):
        # A bare "hostname" payload key also feeds extract_netbox_change_details's
        # host_name/dns_name resolution (see test_reassigned_* / the dns_name
        # fallback chain), so isolating a pure HOSTNAME_CHANGED requires the
        # assignment and dns_name to stay identical while only the separate
        # "hostname" label changes — a realistic shape for sources (GestioIP,
        # phpIPAM) that track a friendly host label independently of DNS name.
        pre = {
            "assigned_object": {"name": "eth0", "device": {"name": "srv01"}},
            "dns_name": "fixed.example.com",
            "hostname": "old-label",
        }
        post = {
            "assigned_object": {"name": "eth0", "device": {"name": "srv01"}},
            "dns_name": "fixed.example.com",
            "hostname": "new-label",
        }
        self.assertEqual(_classify("update", pre, post), EventType.HOSTNAME_CHANGED)

    def test_status_changed_takes_priority_over_assignment_change(self):
        pre = {"assigned_object": {"name": "eth0", "device": {"name": "srv01"}}, "status": "reserved"}
        post = {"assigned_object": {"name": "eth0", "virtual_machine": {"name": "vm01"}}, "status": "active"}
        result = _classify("update", pre, post, pre_status="reserved", post_status="active")
        self.assertEqual(result, EventType.STATUS_CHANGED)

    def test_no_meaningful_change_is_updated(self):
        pre = {"description": "old note"}
        post = {"description": "new note"}
        self.assertEqual(_classify("update", pre, post), EventType.UPDATED)

    def test_unrecognized_action_returns_none_for_caller_fallback(self):
        self.assertIsNone(classify_event_type("snapshot"))


class OwnerTypeGuessTests(TestCase):
    def test_device_from_nested_dict(self):
        self.assertEqual(_guess_owner_type({"assigned_object": {"device": {"name": "srv01"}}}), "device")

    def test_virtualmachine_from_nested_dict(self):
        self.assertEqual(_guess_owner_type({"assigned_object": {"virtual_machine": {"name": "vm01"}}}), "virtualmachine")

    def test_unknown_when_ambiguous(self):
        self.assertEqual(_guess_owner_type({"assigned_object": "srv01 > eth0"}), "")
        self.assertEqual(_guess_owner_type(None), "")

    def test_real_native_payload_shape_with_integer_content_type_pk(self):
        """Regression test: real core.ObjectChange records (produced by
        Django's serialize_object(), not a REST-API-style nested dict) store
        assigned_object_type as a raw ContentType integer PK with NO nested
        "assigned_object" key at all. A live deployment run against actual
        NetBox surfaced this exact shape and found _guess_owner_type
        returning '' for it (silently degrading OWNER_CHANGED to
        REASSIGNED) until it was fixed to delegate to
        resolve_assigned_object_type(), which already handled this shape."""
        interface_ct = SimpleNamespace(pk=7, model="interface")
        vminterface_ct = SimpleNamespace(pk=10, model="vminterface")

        # Payload shapes exactly as observed from a real ObjectChange row.
        device_payload = {
            "address": "10.10.1.40/24", "status": "active", "dns_name": "",
            "assigned_object_id": 2, "assigned_object_type": 7,
        }
        vm_payload = {
            "address": "10.10.1.40/24", "status": "active", "dns_name": "",
            "assigned_object_id": 2, "assigned_object_type": 10,
        }

        class MockContentTypeManager:
            def filter(self, pk):
                ct = {7: interface_ct, 10: vminterface_ct}.get(pk)
                return SimpleNamespace(first=lambda: ct)

        mock_contenttypes = SimpleNamespace(
            models=SimpleNamespace(ContentType=SimpleNamespace(objects=MockContentTypeManager()))
        )

        with mock.patch.dict("sys.modules", {
            "django.contrib.contenttypes": mock_contenttypes,
            "django.contrib.contenttypes.models": mock_contenttypes.models,
        }):
            self.assertEqual(_guess_owner_type(device_payload), "device")
            self.assertEqual(_guess_owner_type(vm_payload), "virtualmachine")

            # End-to-end: given host_name already resolved (as it would be
            # by extract_netbox_change_details's DB-backed Interface/
            # VMInterface lookup in a real environment), the classifier
            # must report OWNER_CHANGED rather than REASSIGNED.
            result = classify_event_type(
                "update", "admin",
                pre_payload=device_payload, post_payload=vm_payload,
                pre_details={"host_name": "ESXI-TEST-01", "interface_name": "vmk1"},
                post_details={"host_name": "VM-DB-01", "interface_name": "eth0"},
            )
            self.assertEqual(result, EventType.OWNER_CHANGED)


class MockObjectChange:
    def __init__(self, pk, address, action="update", user_name="netbox", assigned_object=None):
        self.pk = pk
        self.time = datetime(2026, 2, 6, 8, 16, 0, tzinfo=timezone.utc)
        self.action = action
        self.user_name = user_name
        self.object_repr = address
        post = {"address": address}
        if assigned_object:
            post["assigned_object"] = assigned_object
        self.postchange_data = post
        self.prechange_data = {}


class DuplicateEventPreventionTests(TestCase):
    def test_native_events_excludes_already_synced_pks(self):
        """When an ObjectChange has already been synced into HistoricalIPEvent
        (its pk recorded on the stored event), native_events() must exclude
        it from the live-ObjectChange view to avoid showing the same
        change twice in a merged timeline (see get_timeline())."""
        changes = [
            MockObjectChange(201, "10.0.0.9/24", action="create"),
            MockObjectChange(202, "10.0.0.9/24", action="update", assigned_object="host01 > eth0"),
        ]

        class MockQuerySet:
            def filter(self, *args, **kwargs):
                return self
            def order_by(self, *args, **kwargs):
                return changes

        mock_core = SimpleNamespace(models=SimpleNamespace(ObjectChange=SimpleNamespace(objects=MockQuerySet())))

        with mock.patch.dict("sys.modules", {"core": mock_core, "core.models": mock_core.models}):
            all_events = native_events("10.0.0.9")
            self.assertEqual(len(all_events), 2)

            filtered_events = native_events("10.0.0.9", exclude_pks={"201"})
            self.assertEqual(len(filtered_events), 1)
            self.assertEqual(filtered_events[0]["pk"], 202)


class NativeEventsDatabaseFilterTests(TestCase):
    """Regression guard for a real full-table-scan bug: native_events() used
    to query every ipaddress ObjectChange in the whole installation and
    filter for the requested IP entirely in Python. It must now narrow at
    the database level first (this test asserts that filter is actually
    constructed and passed to the queryset), with the exact Python-side
    match still applied as the correctness authority.

    Note: locally (no Django installed) services/timeline.py's Q falls back
    to a no-op stub, so this test can only verify the filter is *built and
    submitted* to .filter() with the canonical IP referenced somewhere in
    it — not that Postgres would evaluate it correctly. That semantic
    correctness (including the "172.17.8.8" vs "172.17.8.80" boundary) was
    verified directly against a live NetBox/Postgres instance."""

    def test_ip_scoping_filter_is_submitted_to_queryset(self):
        recorded_filter_calls = []

        class MockQuerySet:
            def filter(self, *args, **kwargs):
                recorded_filter_calls.append((args, kwargs))
                return self
            def order_by(self, *args, **kwargs):
                return []

        mock_core = SimpleNamespace(models=SimpleNamespace(ObjectChange=SimpleNamespace(objects=MockQuerySet())))

        with mock.patch.dict("sys.modules", {"core": mock_core, "core.models": mock_core.models}):
            native_events("10.10.1.70")

        # Two .filter() calls are expected: the model-type filter
        # (changed_object_type__model="ipaddress") and the new IP-scoping
        # filter. The IP-scoping call must be a positional Q-like argument
        # (not a bare kwarg), and its string form must reference the
        # canonical IP being searched for.
        self.assertGreaterEqual(len(recorded_filter_calls), 2)
        ip_scoping_calls = [
            call for call in recorded_filter_calls
            if call[0] and "10.10.1.70" in str(call[0][0])
        ]
        self.assertTrue(
            ip_scoping_calls,
            f"Expected a .filter() call referencing the canonical IP; got calls: {recorded_filter_calls}",
        )
