import io
import json
from types import SimpleNamespace
from unittest import TestCase, mock

from netbox_ip_history.api.views import (
    HistoricalIPEventViewSet,
    ImportJobViewSet,
    ImportSourceViewSet,
)
from netbox_ip_history.choices import EventType, JobStatus, SourceType
from netbox_ip_history.filtersets import (
    HistoricalIPEventFilterSet,
    ImportJobFilterSet,
    ImportSourceFilterSet,
)
from netbox_ip_history.importers.generic_csv import GenericCSVImporter
from netbox_ip_history.importers.generic_json import GenericJSONImporter
from netbox_ip_history.importers.gestioip import parse_gestioip_audit_event
from netbox_ip_history.importers.phpipam import PhpIPAMImporter
from netbox_ip_history.models import HistoricalIPEvent, ImportJob, ImportSource
from netbox_ip_history.services.import_service import rollback_job, run_import
from netbox_ip_history.services.owner_resolver import resolve_owner


class MockJob:
    # Not a real Django Model, so under a real Django/DB environment
    # (netbox-matrix.yml's "Run plugin tests with coverage" step, the
    # only place this suite runs against a real ORM) rollback_job()'s
    # `HistoricalIPEvent.objects.filter(import_job=job)` falls through
    # Django's related-lookup machinery straight to `int(job)` on the
    # whole object, since only a genuine Model instance gets its .pk
    # extracted. __int__ makes that coercion succeed with a fake pk that
    # matches zero real rows — fine, since this test only asserts the
    # post-delete status/summary side effects, never the delete count.
    def __int__(self):
        return self.pk

    def __init__(self, source):
        self.source = source
        self.pk = self.id = 999999999
        self.dry_run = False
        self.total_records = 0
        self.processed_records = 0
        self.created_records = 0
        self.updated_records = 0
        self.skipped_records = 0
        self.duplicate_records = 0
        self.conflict_records = 0
        self.error_records = 0
        self.status = JobStatus.RUNNING
        self.summary = {}
        self.error_details = []
        self.completed = None

    def save(self, *args, **kwargs):
        pass


class EnterpriseSecurityAndImportTests(TestCase):
    def setUp(self):
        self.source = SimpleNamespace(
            name="Test phpIPAM",
            slug="phpipam-test",
            source_type=SourceType.PHPIPAM,
            source_timezone="UTC",
            field_mapping={},
        )

    def test_api_viewsets_have_filterset_class(self):
        """Ensure NetBox API viewsets have filtersets attached for full filtering capability."""
        self.assertEqual(ImportSourceViewSet.filterset_class, ImportSourceFilterSet)
        self.assertEqual(ImportJobViewSet.filterset_class, ImportJobFilterSet)
        self.assertEqual(HistoricalIPEventViewSet.filterset_class, HistoricalIPEventFilterSet)

    def test_gestioip_ipv6_audit_event_parsing(self):
        """Ensure GestioIP parser handles IPv6 audit logs cleanly."""
        ipv6_line = "2001:db8::1: down -> up"
        parsed = parse_gestioip_audit_event(ipv6_line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["ip_address"], "2001:db8::1")
        self.assertEqual(parsed["status"], "up")
        self.assertEqual(parsed["event_type"], "status_changed")

        ipv6_cidr_line = "2001:db8::/64,vlan10,Core IPv6 Subnet"
        parsed_cidr = parse_gestioip_audit_event(ipv6_cidr_line)
        self.assertIsNotNone(parsed_cidr)
        self.assertEqual(parsed_cidr["ip_address"], "2001:db8::")
        self.assertEqual(parsed_cidr["prefix_length"], 64)

    def test_generic_json_importer_array_and_jsonl(self):
        """Test standard JSON array and JSON Lines streaming import."""
        # 1. Array format
        json_data = json.dumps([
            {"ip_address": "10.0.0.1", "hostname": "web01", "timestamp": "2025-01-01T12:00:00Z"},
            {"ip_address": "10.0.0.2", "hostname": "db01", "timestamp": "2025-01-01T12:05:00Z"}
        ]).encode("utf-8")
        importer = GenericJSONImporter(self.source, io.BytesIO(json_data))
        records = list(importer.iter_history())
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["ip_address"], "10.0.0.1")
        self.assertEqual(records[1]["hostname"], "db01")

        # 2. JSON Lines format
        jsonl_data = (
            '{"ip_address": "10.0.0.3", "hostname": "app01", "timestamp": "2025-01-01T12:10:00Z"}\n'
            '{"ip_address": "10.0.0.4", "hostname": "cache01", "timestamp": "2025-01-01T12:15:00Z"}\n'
        ).encode("utf-8")
        importer_jsonl = GenericJSONImporter(self.source, io.BytesIO(jsonl_data))
        records_jsonl = list(importer_jsonl.iter_history())
        self.assertEqual(len(records_jsonl), 2)
        self.assertEqual(records_jsonl[0]["ip_address"], "10.0.0.3")

    def test_phpipam_importer_with_aliases(self):
        """Test phpIPAM alias mapping."""
        csv_data = "ip,hostname,device,subnet,date,note\n192.168.10.5,srv01,switch-core,24,2025-01-01 10:00:00,Core Switch\n".encode("utf-8")
        importer = PhpIPAMImporter(self.source, io.BytesIO(csv_data), format="csv")
        records = list(importer.iter_history())
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["ip_address"], "192.168.10.5")
        self.assertEqual(records[0]["hostname"], "srv01")
        self.assertEqual(records[0]["device_name"], "switch-core")
        self.assertEqual(records[0]["prefix_length"], "24")

    def test_run_import_dry_run_and_deduplication(self):
        """Test import simulation mode and in-stream deduplication."""
        csv_data = (
            "ip_address,hostname,timestamp\n"
            "10.1.1.1,host1,2025-01-01T00:00:00Z\n"
            "10.1.1.1,host1,2025-01-01T00:00:00Z\n"  # Duplicate in same stream
            "10.1.1.2,host2,2025-01-01T00:00:00Z\n"
            "invalid-ip,host3,2025-01-01T00:00:00Z\n"  # Error
        ).encode("utf-8")
        importer = GenericCSVImporter(self.source, io.BytesIO(csv_data))
        job = MockJob(self.source)
        job.dry_run = True

        run_import(job, importer, dry_run=True)

        self.assertEqual(job.status, JobStatus.DRY_RUN)
        self.assertEqual(job.total_records, 4)
        self.assertEqual(job.created_records, 2)  # host1, host2
        self.assertEqual(job.duplicate_records, 1)  # duplicate host1
        self.assertEqual(job.error_records, 1)  # invalid-ip
        self.assertEqual(len(job.error_details), 1)

    def test_rollback_job_sets_status_and_summary(self):
        """Test that rollback_job sets status to ROLLED_BACK and records audit counter."""
        job = MockJob(self.source)
        job.status = JobStatus.COMPLETED
        job.summary = {"valid": 5}

        deleted_count = rollback_job(job)
        self.assertEqual(job.status, JobStatus.ROLLED_BACK)
        self.assertIn("rolled_back_events", job.summary)

    def test_owner_resolver_safe_standalone(self):
        """Test that resolve_owner runs safely even without database models."""
        res = resolve_owner(device_name="non-existent-device")
        self.assertIsNone(res)

    def test_import_job_get_absolute_url(self):
        """Test ImportJob absolute URL generator."""
        job = ImportJob()
        url = job.get_absolute_url()
        self.assertTrue(url.startswith("/plugins/ip-history/import-jobs/"))

    def test_native_event_wrapper(self):
        """Test NativeEventWrapper correctly formats NetBox ObjectChange snapshots."""
        from datetime import datetime
        from netbox_ip_history.services.timeline import NativeEventWrapper

        dummy_change = SimpleNamespace(
            pk=101,
            time=datetime(2026, 8, 25, 2, 0, 0),
            action="create",
            user_name="admin_user",
            changed_object_type="ipam.ipaddress",
            postchange_data={
                "address": "192.168.10.50/24",
                "dns_name": "srv01.corp.local",
                "description": "Core Auth Server",
                "assigned_object": {"name": "eth0", "device": {"name": "switch-01"}},
                "vrf": {"name": "Corporate-VRF"},
            },
            prechange_data={},
        )

        wrapper = NativeEventWrapper(dummy_change)
        self.assertEqual(wrapper.pk, 101)
        self.assertEqual(wrapper.ip_address, "192.168.10.50")
        self.assertEqual(wrapper.prefix_length, 24)
        self.assertEqual(wrapper.event_type, "created")
        self.assertEqual(wrapper.source.name, "NetBox")
        self.assertEqual(wrapper.dns_name, "srv01.corp.local")
        self.assertEqual(wrapper.vrf_name, "Corporate-VRF")
        self.assertEqual(wrapper.interface_name, "eth0")
        self.assertEqual(wrapper.owner_name, "switch-01")
        self.assertIn("srv01.corp.local", wrapper.raw_data)

    def test_native_event_status_and_discovery(self):
        """Test status change and auto-discovery recognition in NativeEventWrapper."""
        from datetime import datetime
        from netbox_ip_history.services.timeline import NativeEventWrapper

        # 1. Discovery by ping/scanner
        disc_change = SimpleNamespace(
            pk=102,
            time=datetime(2026, 8, 25, 3, 0, 0),
            action="create",
            user_name="netbox-ping",
            changed_object_type="ipam.ipaddress",
            postchange_data={"address": "10.0.0.5/24", "status": "active"},
            prechange_data={},
        )
        wrapper_disc = NativeEventWrapper(disc_change)
        self.assertEqual(wrapper_disc.event_type, "discovered")
        self.assertEqual(wrapper_disc.get_event_type_display(), "Discovered")

        # 2. Status change from reserved to active
        status_change = SimpleNamespace(
            pk=103,
            time=datetime(2026, 8, 25, 3, 5, 0),
            action="update",
            user_name="admin",
            changed_object_type="ipam.ipaddress",
            postchange_data={"address": "10.0.0.5/24", "status": "active"},
            prechange_data={"address": "10.0.0.5/24", "status": "reserved"},
        )
        wrapper_status = NativeEventWrapper(status_change)
        self.assertEqual(wrapper_status.event_type, "status_changed")
        self.assertEqual(wrapper_status.get_event_type_display(), "Status Changed")

        # 3. Deletion with empty payload but object_repr
        del_change = SimpleNamespace(
            pk=104,
            time=datetime(2026, 8, 25, 3, 10, 0),
            action="delete",
            user_name="admin",
            changed_object_type="ipam.ipaddress",
            object_repr="10.0.0.5/24",
            postchange_data={},
            prechange_data={},
        )
        wrapper_del = NativeEventWrapper(del_change)
        self.assertEqual(wrapper_del.event_type, "deleted")
        self.assertEqual(wrapper_del.ip_address, "10.0.0.5")
        self.assertEqual(wrapper_del.get_event_type_display(), "Deleted")

    def test_search_form_cidr_cleaning(self):
        """Test HistorySearchForm correctly strips CIDR prefix from search queries."""
        from netbox_ip_history.forms import HistorySearchForm
        form = HistorySearchForm(data={"ip": " 172.16.20.10/24 "})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["ip"], "172.16.20.10")


class SignalsPerformanceAndReliabilityTests(TestCase):
    """Regression guards for two issues found in a pre-release audit:
    get_or_create_netbox_source() re-querying on every call (a real N+1 in
    sync_netbox_ip_history's bulk resync loop, which calls it once per
    ObjectChange row), and object_change_receiver logging real failures at
    DEBUG (invisible in typical production log levels), which could let
    native lifecycle tracking silently stop working with no operator ever
    noticing."""

    def setUp(self):
        from netbox_ip_history import signals
        self.signals = signals
        signals._netbox_source_cache.clear()

    def tearDown(self):
        self.signals._netbox_source_cache.clear()

    def test_get_or_create_netbox_source_is_cached_across_calls(self):
        from netbox_ip_history.models import ImportJob, ImportSource

        fake_source = SimpleNamespace(name="NetBox")
        fake_job = SimpleNamespace(filename="native_netbox_sync")
        source_manager = mock.MagicMock()
        source_manager.get_or_create.return_value = (fake_source, True)
        job_manager = mock.MagicMock()
        job_manager.get_or_create.return_value = (fake_job, True)

        with mock.patch.object(ImportSource, "objects", source_manager, create=True), \
             mock.patch.object(ImportJob, "objects", job_manager, create=True):
            source1, job1 = self.signals.get_or_create_netbox_source()
            source2, job2 = self.signals.get_or_create_netbox_source()
            source3, job3 = self.signals.get_or_create_netbox_source()

        self.assertEqual(source_manager.get_or_create.call_count, 1)
        self.assertEqual(job_manager.get_or_create.call_count, 1)
        self.assertIs(source1, source2)
        self.assertIs(source2, source3)
        self.assertIs(job1, job2)
        self.assertIs(job2, job3)

    def test_object_change_receiver_logs_failures_at_warning_not_debug(self):
        instance = SimpleNamespace(
            changed_object_type=SimpleNamespace(model="ipaddress"),
        )
        with mock.patch.object(
            self.signals, "record_object_change_as_event", side_effect=RuntimeError("boom")
        ), mock.patch.object(self.signals.logger, "warning") as mock_warning, \
           mock.patch.object(self.signals.logger, "debug") as mock_debug:
            # Must not raise — a failure recording history must never break
            # the actual NetBox save() that triggered this signal.
            self.signals.object_change_receiver(sender=None, instance=instance, created=True)

        mock_warning.assert_called_once()
        mock_debug.assert_not_called()
        # exc_info=True so the traceback is actually visible in logs, not
        # just the bare "failed" message.
        self.assertTrue(mock_warning.call_args.kwargs.get("exc_info"))
