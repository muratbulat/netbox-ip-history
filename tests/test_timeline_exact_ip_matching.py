import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase, mock

from netbox_ip_history.services.timeline import (
    NativeEventWrapper,
    extract_ip_from_change,
    extract_netbox_change_details,
    native_events,
)


class MockObjectChange:
    def __init__(self, pk, address, action="update", user_name="netbox", object_repr=None, assigned_object=None, postchange_extra=None):
        self.pk = pk
        self.time = datetime(2026, 2, 6, 8, 16, 0, tzinfo=timezone.utc)
        self.action = action
        self.user_name = user_name
        self.object_repr = object_repr or address
        post = {"address": address}
        if assigned_object:
            post["assigned_object"] = assigned_object
        if postchange_extra:
            post.update(postchange_extra)
        self.postchange_data = post
        self.prechange_data = {}


class TimelineExactIPMatchingTests(TestCase):
    def test_extract_ip_from_change_exact(self):
        """Test that extract_ip_from_change correctly extracts canonical IP and prefix length."""
        c1 = MockObjectChange(1, "172.17.8.8/24")
        ip, prefix = extract_ip_from_change(c1)
        self.assertEqual(ip, "172.17.8.8")
        self.assertEqual(prefix, 24)

        c2 = MockObjectChange(2, "172.17.8.85/24")
        ip2, prefix2 = extract_ip_from_change(c2)
        self.assertEqual(ip2, "172.17.8.85")
        self.assertEqual(prefix2, 24)

    def test_native_events_excludes_similar_prefix_ips(self):
        """Test that querying timeline for 172.17.8.8 NEVER matches 172.17.8.80, 172.17.8.85, etc."""
        changes = [
            MockObjectChange(101, "172.17.8.8/24", action="update", assigned_object="vm-app01 > vNIC 1 (Data-VLAN8)"),
            MockObjectChange(102, "172.17.8.80/24", action="create", assigned_object="dmzesxi01.example.test > vmk2"),
            MockObjectChange(103, "172.17.8.85/24", action="create", assigned_object="dmzesxi05.example.test > vmk2"),
            MockObjectChange(104, "172.17.8.89/24", action="update", assigned_object="edge-vm01 > vNIC 1"),
        ]

        class MockQuerySet:
            def filter(self, *args, **kwargs):
                return self
            def order_by(self, *args, **kwargs):
                return changes

        mock_core = SimpleNamespace(
            models=SimpleNamespace(
                ObjectChange=SimpleNamespace(
                    objects=MockQuerySet()
                )
            )
        )

        with mock.patch.dict("sys.modules", {"core": mock_core, "core.models": mock_core.models}):
            events = native_events("172.17.8.8")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["ip_address"], "172.17.8.8")
            self.assertEqual(events[0]["owner_name"], "vm-app01")
            self.assertEqual(events[0]["interface_name"], "vNIC 1 (Data-VLAN8)")

    def test_extract_netbox_change_details_host_and_interface_separation(self):
        """Test that interface names are not mistakenly assigned as host names."""
        # 1. Combined host > interface string
        d1 = extract_netbox_change_details({"assigned_object": "vm-app01 > vNIC 1 (Data-VLAN8)"})
        self.assertEqual(d1["host_name"], "vm-app01")
        self.assertEqual(d1["interface_name"], "vNIC 1 (Data-VLAN8)")

        # 2. Standalone interface string without parent
        d2 = extract_netbox_change_details({"assigned_object": "vmk2 (iLO)"})
        self.assertEqual(d2["host_name"], "")
        self.assertEqual(d2["interface_name"], "vmk2 (iLO)")

        # 3. Nested dictionary
        d3 = extract_netbox_change_details({
            "assigned_object": {
                "name": "vNIC 1",
                "virtual_machine": {"name": "vm-app01"}
            }
        })
        self.assertEqual(d3["host_name"], "vm-app01")
        self.assertEqual(d3["interface_name"], "vNIC 1")

    def test_resolve_assigned_object_type(self):
        """Test accurate resolution of assigned_object_type from dict, str, and IDs."""
        from netbox_ip_history.services.timeline import resolve_assigned_object_type

        self.assertEqual(resolve_assigned_object_type({"assigned_object_type": "dcim.interface"}), "interface")
        self.assertEqual(resolve_assigned_object_type({"assigned_object_type": "virtualization.vminterface"}), "vminterface")
        self.assertEqual(resolve_assigned_object_type({"assigned_object_type": {"app_label": "dcim", "model": "interface"}}), "interface")
        self.assertEqual(resolve_assigned_object_type({"assigned_object_type": {"app_label": "virtualization", "model": "vminterface"}}), "vminterface")
        self.assertEqual(resolve_assigned_object_type({"assigned_object": {"url": "/api/dcim/interfaces/50/"}}), "interface")
        self.assertEqual(resolve_assigned_object_type({"assigned_object": {"url": "/api/virtualization/interfaces/50/"}}), "vminterface")

    def test_dns_name_fallback_to_device(self):
        """When assigned_object is missing or unassigned, host_name falls back to device matching dns_name."""
        mock_device = SimpleNamespace(name="esxi08.example.test")

        class MockDeviceQuerySet:
            def filter(self, name__iexact):
                return self
            def first(self):
                return mock_device

        mock_dcim = SimpleNamespace(models=SimpleNamespace(Device=SimpleNamespace(objects=MockDeviceQuerySet())))

        with mock.patch.dict("sys.modules", {"dcim": mock_dcim, "dcim.models": mock_dcim.models}):
            d = extract_netbox_change_details({
                "dns_name": "esxi08.example.test",
                "assigned_object_id": None,
            })
            self.assertEqual(d["host_name"], "esxi08.example.test")
            self.assertEqual(d["dns_name"], "esxi08.example.test")

    def test_device_interface_resolution_avoids_vm_collision(self):
        """Ensure device interface ID (e.g. esxi08.example.test) is not overridden by VMInterface with same ID (edge-vm02)."""
        mock_device = SimpleNamespace(name="esxi08.example.test")
        mock_interface = SimpleNamespace(name="vmk2", device=mock_device)
        mock_vm = SimpleNamespace(name="edge-vm02")
        mock_vminterface = SimpleNamespace(name="vNIC 1", virtual_machine=mock_vm)

        class MockInterfaceQuerySet:
            def filter(self, pk):
                return self
            def select_related(self, *args):
                return self
            def first(self):
                return mock_interface

        class MockVMInterfaceQuerySet:
            def filter(self, pk):
                return self
            def select_related(self, *args):
                return self
            def first(self):
                return mock_vminterface

        mock_dcim = SimpleNamespace(models=SimpleNamespace(Interface=SimpleNamespace(objects=MockInterfaceQuerySet())))
        mock_virt = SimpleNamespace(models=SimpleNamespace(VMInterface=SimpleNamespace(objects=MockVMInterfaceQuerySet())))

        with mock.patch.dict("sys.modules", {"dcim": mock_dcim, "dcim.models": mock_dcim.models, "virtualization": mock_virt, "virtualization.models": mock_virt.models}):
            # Payload specifying dcim.interface must resolve to esxi08.example.test, NOT edge-vm02
            d = extract_netbox_change_details({
                "assigned_object_id": 50,
                "assigned_object_type": "dcim.interface",
            })
            self.assertEqual(d["host_name"], "esxi08.example.test")
            self.assertEqual(d["interface_name"], "vmk2")

            # Payload specifying virtualization.vminterface must resolve to edge-vm02
            d_vm = extract_netbox_change_details({
                "assigned_object_id": 50,
                "assigned_object_type": "virtualization.vminterface",
            })
            self.assertEqual(d_vm["host_name"], "edge-vm02")
            self.assertEqual(d_vm["interface_name"], "vNIC 1")

    def test_dns_consistency_check_overrides_accidental_vm_collision(self):
        """If dns_name is a known Device (esxi08.example.test) but host was resolved to a VM (edge-vm02), Device wins."""
        class MockDeviceQuerySet:
            def filter(self, name__iexact):
                class ExistsQuery:
                    def exists(self):
                        return name__iexact == "esxi08.example.test"
                return ExistsQuery()

        class MockVMQuerySet:
            def filter(self, name__iexact):
                class ExistsQuery:
                    def exists(self):
                        return name__iexact == "edge-vm02"
                return ExistsQuery()

        mock_dcim = SimpleNamespace(models=SimpleNamespace(Device=SimpleNamespace(objects=MockDeviceQuerySet())))
        mock_virt = SimpleNamespace(models=SimpleNamespace(VirtualMachine=SimpleNamespace(objects=MockVMQuerySet())))

        with mock.patch.dict("sys.modules", {"dcim": mock_dcim, "dcim.models": mock_dcim.models, "virtualization": mock_virt, "virtualization.models": mock_virt.models}):
            d = extract_netbox_change_details({
                "dns_name": "esxi08.example.test",
                "virtual_machine": {"name": "edge-vm02"},
            })
            self.assertEqual(d["host_name"], "esxi08.example.test")
            self.assertEqual(d["dns_name"], "esxi08.example.test")
