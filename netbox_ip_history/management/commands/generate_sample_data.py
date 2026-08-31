"""
Development-only NetBox sample-data generator for testing netbox_ip_history.

Creates a small, clearly-marked, idempotent DCIM/virtualization/IPAM topology
using only RFC1918 test ranges and obviously non-production names, then
drives a set of IP address lifecycle transitions (assignment, unassignment,
reassignment, device<->VM ownership changes, interface changes, DNS/status
changes, deletion+recreation) through *real* Django ORM operations.

Those operations are wrapped in NetBox's own change-logging context
(netbox.context_managers.event_tracking) so core.ObjectChange rows are
created exactly as they would be from real UI/API activity — which is what
lets netbox_ip_history's signal handler (signals.connect_signals) pick them
up and build native HistoricalIPEvent history, the same as in production use.

NEVER RUN THIS AGAINST A PRODUCTION NETBOX INSTANCE. Every top-level object
is tagged "sample-data" and descriptions are prefixed accordingly, but the
command still creates real Sites/Devices/VMs/IPAddresses.

Idempotent: infrastructure objects are looked up by name/slug and reused if
present. Each lifecycle scenario is keyed to a fixed IP address; if that
address already exists, the scenario is skipped (assumed already run) rather
than duplicating history.
"""
import uuid

from django.core.management.base import BaseCommand


SAMPLE_TAG_SLUG = "sample-data"
SAMPLE_TAG_NAME = "Sample Data"


class Command(BaseCommand):
    help = (
        "Populate NetBox with clearly-marked sample/test data (RFC1918 ranges only) "
        "and drive IP lifecycle scenarios through real ORM operations, for developing "
        "and testing netbox_ip_history. Do not run against a production instance."
    )

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation prompt.")

    def handle(self, *args, **options):
        if not options["yes"]:
            self.stdout.write(self.style.WARNING(
                "This creates sample DCIM/IPAM/virtualization objects (RFC1918 test "
                "ranges, clearly non-production names) and drives IP lifecycle events "
                "through real NetBox ORM operations. Intended for development/test "
                "NetBox instances only.\n"
            ))
            try:
                answer = input("Type 'yes' to continue: ").strip().lower()
            except EOFError:
                answer = ""
            if answer != "yes":
                self.stdout.write("Aborted.")
                return

        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        self.RequestFactory = RequestFactory
        self.actor = get_user_model().objects.get_or_create(
            username="sampledata-generator",
            defaults={"first_name": "Sample Data", "last_name": "Generator", "is_active": True},
        )[0]
        if self.actor.has_usable_password():
            self.actor.set_unusable_password()
            self.actor.save()

        self.created_counts = {}
        self.scenario_results = []

        topology = self._build_topology()
        self._run_lifecycle_scenarios(topology)

        self.stdout.write(self.style.SUCCESS(
            "\nSample data generation complete.\n"
            f"Topology objects created/verified: {sum(self.created_counts.values())} "
            f"({', '.join(f'{k}={v}' for k, v in self.created_counts.items())})\n"
            f"Lifecycle scenarios: {len(self.scenario_results)}\n"
            + "\n".join(f"  - {name}: {status}" for name, status in self.scenario_results)
        ))

    # -- infrastructure -----------------------------------------------------

    def _request(self):
        request = self.RequestFactory().get("/")
        request.id = uuid.uuid4()
        request.user = self.actor
        return request

    def _track(self, kind, created):
        self.created_counts[kind] = self.created_counts.get(kind, 0) + (1 if created else 0)

    def _build_topology(self):
        from netbox.context_managers import event_tracking

        with event_tracking(self._request()):
            self._sample_tag = self._get_or_create_tag()
            objs = {}

            objs["tenant"] = self._get_or_create(
                "tenancy.models", "Tenant", "tenant", name="Sample Test Tenant", slug="sample-test-tenant",
                defaults={"description": "[sample-data] Non-production tenant for netbox_ip_history testing."},
            )

            objs["site_ankara"] = self._get_or_create(
                "dcim.models", "Site", "site", name="SITE-ANKARA", slug="site-ankara",
                defaults={"status": "active", "description": "[sample-data] Test site (Ankara)."},
            )
            objs["site_istanbul"] = self._get_or_create(
                "dcim.models", "Site", "site", name="SITE-ISTANBUL", slug="site-istanbul",
                defaults={"status": "active", "description": "[sample-data] Test site (Istanbul)."},
            )

            objs["loc_ankara"] = self._get_or_create(
                "dcim.models", "Location", "location", name="LOC-ANKARA-DC01", slug="loc-ankara-dc01",
                defaults={"site": objs["site_ankara"], "status": "active"},
            )
            objs["loc_istanbul"] = self._get_or_create(
                "dcim.models", "Location", "location", name="LOC-ISTANBUL-DC01", slug="loc-istanbul-dc01",
                defaults={"site": objs["site_istanbul"], "status": "active"},
            )

            objs["rack_a01"] = self._get_or_create(
                "dcim.models", "Rack", "rack", name="RACK-A01",
                defaults={"site": objs["site_ankara"], "location": objs["loc_ankara"], "status": "active"},
            )
            objs["rack_b01"] = self._get_or_create(
                "dcim.models", "Rack", "rack", name="RACK-B01",
                defaults={"site": objs["site_istanbul"], "location": objs["loc_istanbul"], "status": "active"},
            )

            objs["manufacturer"] = self._get_or_create(
                "dcim.models", "Manufacturer", "manufacturer", name="Generic Test Manufacturing", slug="generic-test-mfg",
            )
            objs["devicetype_server"] = self._get_or_create(
                "dcim.models", "DeviceType", "device_type", model="TEST-SERVER-1U", slug="test-server-1u",
                defaults={"manufacturer": objs["manufacturer"], "u_height": 1},
            )
            objs["devicetype_switch"] = self._get_or_create(
                "dcim.models", "DeviceType", "device_type", model="TEST-SWITCH-1U", slug="test-switch-1u",
                defaults={"manufacturer": objs["manufacturer"], "u_height": 1},
            )

            objs["role_hypervisor"] = self._get_or_create(
                "dcim.models", "DeviceRole", "device_role", name="Test Hypervisor", slug="test-hypervisor",
                defaults={"color": "2196f3", "vm_role": False},
            )
            objs["role_switch"] = self._get_or_create(
                "dcim.models", "DeviceRole", "device_role", name="Test Switch", slug="test-switch",
                defaults={"color": "4caf50", "vm_role": False},
            )

            objs["platform_esxi"] = self._get_or_create(
                "dcim.models", "Platform", "platform", name="Test ESXi", slug="test-esxi",
            )
            objs["platform_nos"] = self._get_or_create(
                "dcim.models", "Platform", "platform", name="Test Network OS", slug="test-network-os",
            )
            objs["platform_linux"] = self._get_or_create(
                "dcim.models", "Platform", "platform", name="Test Linux", slug="test-linux",
            )

            objs["dev_esxi01"] = self._get_or_create(
                "dcim.models", "Device", "device", name="ESXI-TEST-01",
                defaults={
                    "device_type": objs["devicetype_server"], "role": objs["role_hypervisor"],
                    "platform": objs["platform_esxi"], "site": objs["site_ankara"],
                    "location": objs["loc_ankara"], "rack": objs["rack_a01"], "position": 10,
                    "face": "front", "status": "active", "tenant": objs["tenant"],
                    "description": "[sample-data] Test ESXi hypervisor host.",
                },
            )
            objs["dev_sw01"] = self._get_or_create(
                "dcim.models", "Device", "device", name="SW-TEST-01",
                defaults={
                    "device_type": objs["devicetype_switch"], "role": objs["role_switch"],
                    "platform": objs["platform_nos"], "site": objs["site_ankara"],
                    "location": objs["loc_ankara"], "rack": objs["rack_a01"], "position": 20,
                    "face": "front", "status": "active", "tenant": objs["tenant"],
                    "description": "[sample-data] Test top-of-rack switch (Ankara).",
                },
            )
            objs["dev_sw02"] = self._get_or_create(
                "dcim.models", "Device", "device", name="SW-TEST-02",
                defaults={
                    "device_type": objs["devicetype_switch"], "role": objs["role_switch"],
                    "platform": objs["platform_nos"], "site": objs["site_istanbul"],
                    "location": objs["loc_istanbul"], "rack": objs["rack_b01"], "position": 20,
                    "face": "front", "status": "active", "tenant": objs["tenant"],
                    "description": "[sample-data] Test top-of-rack switch (Istanbul).",
                },
            )

            for dev_key, iface_names in (
                ("dev_esxi01", ("vmk0", "vmk1")),
                ("dev_sw01", ("Gi0/1", "Gi0/2")),
                ("dev_sw02", ("Gi0/1", "Gi0/2")),
            ):
                for name in iface_names:
                    objs[f"iface_{dev_key}_{name}"] = self._get_or_create_interface(objs[dev_key], name)

            objs["clustertype"] = self._get_or_create(
                "virtualization.models", "ClusterType", "cluster_type", name="Test vSphere", slug="test-vsphere",
            )
            objs["cluster"] = self._get_or_create(
                "virtualization.models", "Cluster", "cluster", name="CLUSTER-TEST-01",
                defaults={"type": objs["clustertype"], "scope": objs["site_ankara"], "status": "active"},
            )

            objs["vm_web01"] = self._get_or_create(
                "virtualization.models", "VirtualMachine", "virtual_machine", name="VM-WEB-01",
                defaults={
                    "cluster": objs["cluster"], "site": objs["site_ankara"], "platform": objs["platform_linux"],
                    "status": "active", "tenant": objs["tenant"], "vcpus": 2, "memory": 4096, "disk": 40,
                    "description": "[sample-data] Test web server VM.",
                },
            )
            objs["vm_db01"] = self._get_or_create(
                "virtualization.models", "VirtualMachine", "virtual_machine", name="VM-DB-01",
                defaults={
                    "cluster": objs["cluster"], "site": objs["site_ankara"], "platform": objs["platform_linux"],
                    "status": "active", "tenant": objs["tenant"], "vcpus": 4, "memory": 8192, "disk": 100,
                    "description": "[sample-data] Test database server VM.",
                },
            )
            for vm_key in ("vm_web01", "vm_db01"):
                objs[f"iface_{vm_key}_eth0"] = self._get_or_create_vminterface(objs[vm_key], "eth0")

            from utilities.data import string_to_ranges
            objs["vlangroup"] = self._get_or_create(
                "ipam.models", "VLANGroup", "vlan_group", name="VLANGROUP-ANKARA", slug="vlangroup-ankara",
                defaults={"vid_ranges": string_to_ranges("1-4094")},
            )
            objs["vlan_servers"] = self._get_or_create(
                "ipam.models", "VLAN", "vlan", name="VLAN-TEST-SERVERS", vid=100,
                defaults={"group": objs["vlangroup"], "site": objs["site_ankara"], "status": "active"},
            )
            objs["vlan_vms"] = self._get_or_create(
                "ipam.models", "VLAN", "vlan", name="VLAN-TEST-VMS", vid=200,
                defaults={"group": objs["vlangroup"], "site": objs["site_ankara"], "status": "active"},
            )

            objs["vrf"] = self._get_or_create(
                "ipam.models", "VRF", "vrf", name="VRF-TEST-01",
                defaults={"rd": "65000:100", "description": "[sample-data] Test VRF."},
            )

            objs["prefix_ankara"] = self._get_or_create(
                "ipam.models", "Prefix", "prefix", prefix="10.10.0.0/16",
                defaults={"scope": objs["site_ankara"], "status": "active", "description": "[sample-data] Ankara site aggregate."},
            )
            objs["prefix_ankara_servers"] = self._get_or_create(
                "ipam.models", "Prefix", "prefix", prefix="10.10.1.0/24",
                defaults={"scope": objs["site_ankara"], "vlan": objs["vlan_servers"], "status": "active",
                          "description": "[sample-data] Ankara lifecycle-scenario range."},
            )
            objs["prefix_istanbul"] = self._get_or_create(
                "ipam.models", "Prefix", "prefix", prefix="10.20.0.0/16",
                defaults={"scope": objs["site_istanbul"], "status": "active", "description": "[sample-data] Istanbul site aggregate."},
            )
            objs["prefix_vrf_mgmt"] = self._get_or_create(
                "ipam.models", "Prefix", "prefix", prefix="172.16.10.0/24",
                defaults={"vrf": objs["vrf"], "status": "active", "description": "[sample-data] VRF-scoped management range."},
            )
            objs["prefix_shared"] = self._get_or_create(
                "ipam.models", "Prefix", "prefix", prefix="192.168.100.0/24",
                defaults={"status": "active", "description": "[sample-data] Shared/global-VRF services range."},
            )

            self._assign_base_ips(objs)

        return objs

    def _get_or_create_tag(self):
        from extras.models import Tag
        tag, created = Tag.objects.get_or_create(
            slug=SAMPLE_TAG_SLUG,
            defaults={"name": SAMPLE_TAG_NAME, "color": "e91e63",
                      "description": "Generated by netbox_ip_history's generate_sample_data command."},
        )
        self._track("tag", created)
        return tag

    def _get_or_create(self, module_path, class_name, kind, defaults=None, **lookup):
        import importlib
        model = getattr(importlib.import_module(module_path), class_name)
        obj, created = model.objects.get_or_create(defaults=defaults or {}, **lookup)
        self._track(kind, created)
        if created and hasattr(obj, "tags"):
            obj.tags.add(self._sample_tag)
        return obj

    def _get_or_create_interface(self, device, name):
        from dcim.choices import InterfaceTypeChoices
        from dcim.models import Interface
        iface, created = Interface.objects.get_or_create(
            device=device, name=name,
            defaults={"type": InterfaceTypeChoices.TYPE_1GE_FIXED, "enabled": True},
        )
        self._track("interface", created)
        return iface

    def _get_or_create_vminterface(self, vm, name):
        from virtualization.models import VMInterface
        iface, created = VMInterface.objects.get_or_create(
            virtual_machine=vm, name=name, defaults={"enabled": True},
        )
        self._track("vminterface", created)
        return iface

    def _assign_base_ip(self, address, assigned_object, vrf=None, dns_name="", description="", primary_for=None):
        """Create (if missing) a non-scenario IP used for topology richness /
        primary-IP demonstration. Not part of the tracked lifecycle scenarios."""
        from ipam.models import IPAddress
        ip, created = IPAddress.objects.get_or_create(
            address=address, vrf=vrf,
            defaults={
                "status": "active", "assigned_object": assigned_object,
                "dns_name": dns_name, "description": f"[sample-data] {description}",
            },
        )
        self._track("ip_address", created)
        if created:
            ip.tags.add(self._sample_tag)
        if primary_for is not None and created:
            primary_for.primary_ip4 = ip
            primary_for.save()
        return ip

    def _assign_base_ips(self, objs):
        self._assign_base_ip("10.10.0.10/24", objs["iface_dev_esxi01_vmk0"],
                              dns_name="esxi-test-01.sample.local", description="ESXI-TEST-01 management IP.",
                              primary_for=objs["dev_esxi01"])
        self._assign_base_ip("10.10.0.11/24", objs["iface_dev_sw01_Gi0/1"],
                              dns_name="sw-test-01.sample.local", description="SW-TEST-01 management IP.",
                              primary_for=objs["dev_sw01"])
        self._assign_base_ip("10.20.0.12/24", objs["iface_dev_sw02_Gi0/1"],
                              dns_name="sw-test-02.sample.local", description="SW-TEST-02 management IP.",
                              primary_for=objs["dev_sw02"])
        self._assign_base_ip("10.10.0.20/24", objs["iface_vm_web01_eth0"],
                              dns_name="vm-web-01.sample.local", description="VM-WEB-01 primary IP.",
                              primary_for=objs["vm_web01"])
        self._assign_base_ip("10.10.0.21/24", objs["iface_vm_db01_eth0"],
                              dns_name="vm-db-01.sample.local", description="VM-DB-01 primary IP.",
                              primary_for=objs["vm_db01"])
        self._assign_base_ip("172.16.10.10/24", objs["iface_dev_sw02_Gi0/2"], vrf=objs["vrf"],
                              dns_name="sw-test-02-mgmt.sample.local", description="SW-TEST-02 VRF-scoped mgmt IP.")
        self._assign_base_ip("192.168.100.10/24", objs["iface_dev_esxi01_vmk1"],
                              dns_name="esxi-test-01-shared.sample.local", description="ESXI-TEST-01 shared-services IP.")

    # -- lifecycle scenarios --------------------------------------------------

    def _scenario(self, name, address, fn):
        """Run one lifecycle scenario unless its IP address already exists
        (idempotency: assume a prior run already generated its history)."""
        from ipam.models import IPAddress
        if IPAddress.objects.filter(address=address).exists():
            self.scenario_results.append((name, f"skipped ({address} already exists)"))
            return
        fn()
        self.scenario_results.append((name, f"ok ({address})"))

    def _run_lifecycle_scenarios(self, objs):
        from ipam.models import IPAddress
        from netbox.context_managers import event_tracking

        def step(fn):
            with event_tracking(self._request()):
                fn()

        def new_ip(address, description, **extra):
            ip = IPAddress(address=address, status="active", description=f"[sample-data] {description}", **extra)
            ip.save()
            ip.tags.add(self._sample_tag)
            return ip

        def reassign(ip, assigned_object):
            ip.snapshot()
            ip.assigned_object = assigned_object
            ip.save()

        def unassign(ip):
            ip.snapshot()
            ip.assigned_object = None
            ip.save()

        # 1 & 3: assign to a physical device interface, then unassign it.
        def scenario_assign_device_then_unassign():
            def do_create():
                self._scn_ip_1 = new_ip("10.10.1.10/24", "Scenario 1/3: device-interface assign + unassign.")
            step(do_create)

            def do_assign():
                reassign(self._scn_ip_1, objs["iface_dev_esxi01_vmk0"])
            step(do_assign)

            def do_unassign():
                unassign(self._scn_ip_1)
            step(do_unassign)
        self._scenario("1+3: assign to device interface, then unassign", "10.10.1.10/24", scenario_assign_device_then_unassign)

        # 2: assign to a VM interface.
        def scenario_assign_vm():
            def do_create():
                self._scn_ip_2 = new_ip("10.10.1.20/24", "Scenario 2: VM-interface assignment.")
            step(do_create)

            def do_assign():
                reassign(self._scn_ip_2, objs["iface_vm_web01_eth0"])
            step(do_assign)
        self._scenario("2: assign to VM interface", "10.10.1.20/24", scenario_assign_vm)

        # 4: reassigned to another owner of the same type (VM -> VM).
        def scenario_reassign_vm_to_vm():
            def do_create():
                self._scn_ip_4 = new_ip("10.10.1.30/24", "Scenario 4: VM-to-VM reassignment.",
                                         assigned_object=objs["iface_vm_web01_eth0"])
            step(do_create)

            def do_reassign():
                reassign(self._scn_ip_4, objs["iface_vm_db01_eth0"])
            step(do_reassign)
        self._scenario("4: reassigned to another owner (VM->VM)", "10.10.1.30/24", scenario_reassign_vm_to_vm)

        # 5: device -> VM ownership change.
        def scenario_device_to_vm():
            def do_create():
                self._scn_ip_5 = new_ip("10.10.1.40/24", "Scenario 5: device-to-VM ownership change.",
                                         assigned_object=objs["iface_dev_esxi01_vmk1"])
            step(do_create)

            def do_move():
                reassign(self._scn_ip_5, objs["iface_vm_db01_eth0"])
            step(do_move)
        self._scenario("5: device -> VM ownership change", "10.10.1.40/24", scenario_device_to_vm)

        # 6: VM -> device ownership change.
        def scenario_vm_to_device():
            def do_create():
                self._scn_ip_6 = new_ip("10.10.1.50/24", "Scenario 6: VM-to-device ownership change.",
                                         assigned_object=objs["iface_vm_web01_eth0"])
            step(do_create)

            def do_move():
                reassign(self._scn_ip_6, objs["iface_dev_sw01_Gi0/2"])
            step(do_move)
        self._scenario("6: VM -> device ownership change", "10.10.1.50/24", scenario_vm_to_device)

        # 7: DNS name change.
        def scenario_dns_change():
            def do_create():
                self._scn_ip_7 = new_ip("10.10.1.60/24", "Scenario 7: DNS name change.",
                                         dns_name="old-host.sample.local")
            step(do_create)

            def do_dns_change():
                self._scn_ip_7.snapshot()
                self._scn_ip_7.dns_name = "new-host.sample.local"
                self._scn_ip_7.save()
            step(do_dns_change)
        self._scenario("7: DNS name change", "10.10.1.60/24", scenario_dns_change)

        # 8: interface change (same device, different interface).
        def scenario_interface_change():
            def do_create():
                self._scn_ip_8 = new_ip("10.10.1.70/24", "Scenario 8: interface change (same device).",
                                         assigned_object=objs["iface_dev_sw01_Gi0/1"])
            step(do_create)

            def do_iface_change():
                reassign(self._scn_ip_8, objs["iface_dev_sw01_Gi0/2"])
            step(do_iface_change)
        self._scenario("8: interface change (same device)", "10.10.1.70/24", scenario_interface_change)

        # 9: status change.
        def scenario_status_change():
            def do_create():
                self._scn_ip_9 = new_ip("10.10.1.80/24", "Scenario 9: status change.")
            step(do_create)

            def do_status_change():
                self._scn_ip_9.snapshot()
                self._scn_ip_9.status = "deprecated"
                self._scn_ip_9.save()
            step(do_status_change)
        self._scenario("9: status change", "10.10.1.80/24", scenario_status_change)

        # 10: deletion and recreation of the same address.
        def scenario_delete_and_recreate():
            def do_create():
                self._scn_ip_10 = new_ip("10.10.1.90/24", "Scenario 10: deletion + recreation.")
            step(do_create)

            def do_delete():
                self._scn_ip_10.delete()
            step(do_delete)

            def do_recreate():
                new_ip("10.10.1.90/24", "Scenario 10: recreated after deletion.")
            step(do_recreate)
        self._scenario("10: deletion and recreation", "10.10.1.90/24", scenario_delete_and_recreate)
