from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from ipam.models import IPAddress
from netbox.registry import registry
from utilities.testing import TestCase

from netbox_ip_history.choices import ImportStatusChoices
from netbox_ip_history.models import HistoricalIPEvent, ImportJob

from .helpers import ip_change, make_source

CSV = b"timestamp,ip,event_type,hostname\n2026-01-01T00:00:00+00:00,192.0.2.60,created,device-01.example.com\n"


def url(name, *args):
    return reverse(f"plugins:netbox_ip_history:{name}", args=args)


@override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=[])
class UIPermissionTests(TestCase):
    def setUp(self):
        super().setUp()
        self.source = make_source(source_timezone="UTC")
        ip_change("192.0.2.60/24")

    def test_workflow_views_are_default_closed(self):
        for name in ("timeline", "compare", "import", "source_support"):
            with self.subTest(view=name):
                self.assertEqual(self.client.get(url(name)).status_code, 403)

    def test_anonymous_users_are_redirected_to_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(url("timeline")).status_code, 302)

    def test_model_views_require_permissions(self):
        for name in ("importsource_list", "importjob_list", "historicalipevent_list"):
            with self.subTest(view=name):
                self.assertEqual(self.client.get(url(name)).status_code, 403)
        self.add_permissions(
            "netbox_ip_history.view_importsource",
            "netbox_ip_history.view_importjob",
            "netbox_ip_history.view_historicalipevent",
        )
        for name in ("importsource_list", "importjob_list", "historicalipevent_list"):
            with self.subTest(view=name):
                self.assertEqual(self.client.get(url(name)).status_code, 200)
        event = HistoricalIPEvent.objects.first()
        self.assertEqual(self.client.get(event.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.source.get_absolute_url()).status_code, 200)

    def test_timeline_and_exports(self):
        self.add_permissions("netbox_ip_history.view_historicalipevent")
        response = self.client.get(url("timeline"), {"ip": "192.0.2.60"})
        self.assertContains(response, "192.0.2.60")
        response = self.client.get(url("timeline"), {"ip": "192.0.2.60", "export": "csv"})
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(b"192.0.2.60", response.content)
        response = self.client.get(url("timeline"), {"ip": "192.0.2.600"})
        self.assertContains(response, "Enter a valid IPv4 or IPv6 address")
        self.assertEqual(self.client.get(url("compare"), {"ip": "192.0.2.60"}).status_code, 200)

    def test_object_permissions_restrict_timeline(self):
        self.add_permissions("netbox_ip_history.view_historicalipevent")
        from users.models import ObjectPermission

        ObjectPermission.objects.filter(users=self.user).update(constraints={"source__slug": "nothing"})
        response = self.client.get(url("timeline"), {"ip": "192.0.2.60"})
        self.assertEqual(response.context["events"], [])

    def test_ipaddress_tab_enforces_plugin_permission(self):
        ip = IPAddress.objects.create(address="192.0.2.61/24")
        tab = reverse("ipam:ipaddress_ip_history", args=[ip.pk])
        self.add_permissions("ipam.view_ipaddress")
        self.assertEqual(self.client.get(tab).status_code, 403)
        self.add_permissions("netbox_ip_history.view_historicalipevent")
        self.assertEqual(self.client.get(tab).status_code, 200)

    def test_dry_run_upload_persists_nothing(self):
        self.add_permissions(
            "netbox_ip_history.view_importsource",
            "netbox_ip_history.add_historicalipevent",
            "netbox_ip_history.add_importjob",
        )
        response = self.client.post(
            url("import"),
            {"source": self.source.pk, "format": "csv", "delimiter": ",", "dry_run": "on",
             "file": SimpleUploadedFile("history.csv", CSV)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["result"].created, 1)
        self.assertFalse(ImportJob.objects.exists())
        self.assertFalse(HistoricalIPEvent.objects.filter(source=self.source).exists())

    def test_live_upload_creates_job(self):
        self.add_permissions(
            "netbox_ip_history.view_importsource",
            "netbox_ip_history.add_historicalipevent",
            "netbox_ip_history.add_importjob",
        )
        response = self.client.post(
            url("import"),
            {"source": self.source.pk, "format": "csv", "delimiter": ",", "file": SimpleUploadedFile("h.csv", CSV)},
        )
        job = ImportJob.objects.get()
        self.assertRedirects(response, job.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(job.status, ImportStatusChoices.COMPLETED)
        self.assertEqual(job.events.count(), 1)

    def test_import_rejects_format_the_source_cannot_parse(self):
        self.add_permissions(
            "netbox_ip_history.view_importsource",
            "netbox_ip_history.add_historicalipevent",
            "netbox_ip_history.add_importjob",
        )
        response = self.client.post(
            url("import"),
            {"source": self.source.pk, "format": "xml", "file": SimpleUploadedFile("h.xml", b"<x/>")},
        )
        self.assertContains(response, "imports accept")

    def test_rollback_requires_permission(self):
        job = ImportJob.objects.create(source=self.source, status=ImportStatusChoices.COMPLETED)
        self.assertEqual(self.client.post(url("importjob_rollback", job.pk)).status_code, 403)
        self.add_permissions("netbox_ip_history.delete_historicalipevent", "netbox_ip_history.change_importjob")
        self.client.post(url("importjob_rollback", job.pk))
        job.refresh_from_db()
        self.assertEqual(job.status, ImportStatusChoices.ROLLED_BACK)


@override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=[])
class APITests(TestCase):
    def setUp(self):
        super().setUp()
        ip_change("2001:db8::60/64")

    def api(self, name, **params):
        return self.client.get(reverse(f"plugins-api:netbox_ip_history-api:{name}"), params)

    def test_timeline_and_compare_require_permission(self):
        self.assertEqual(self.api("timeline", ip="2001:db8::60").status_code, 403)
        self.assertEqual(self.api("compare", ip="2001:db8::60").status_code, 403)

    def test_timeline(self):
        self.add_permissions("netbox_ip_history.view_historicalipevent")
        response = self.api("timeline", ip="2001:0db8:0::0060")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["ip_address"], "2001:db8::60")
        self.assertEqual(response.json()[0]["vrf"], "Global")
        self.assertEqual(self.api("timeline", ip="nonsense").status_code, 400)
        self.assertEqual(self.api("compare", ip="2001:db8::60").json()[0]["source"], "NetBox")

    def test_model_endpoints(self):
        self.add_permissions("netbox_ip_history.view_historicalipevent")
        response = self.api("historicalipevent-list", ip_address="2001:db8::60")
        self.assertEqual(response.json()["count"], 1)
        self.assertIn("display", response.json()["results"][0])
        self.assertEqual(self.api("importsource-list").status_code, 403)


class RegistrationTests(TestCase):
    def test_search_indexes_registered(self):
        self.assertIn("netbox_ip_history.historicalipevent", registry["search"])
        self.assertIn("netbox_ip_history.importsource", registry["search"])

    def test_menu_items_are_permission_gated(self):
        from netbox_ip_history.navigation import menu

        for group in menu.groups:
            for item in group.items:
                self.assertTrue(item.permissions, item.link)


class PageRenderTests(TestCase):
    user_permissions = [
        f"netbox_ip_history.{action}_{model}"
        for action in ("view", "add", "change", "delete")
        for model in ("importsource", "importjob", "historicalipevent")
    ] + ["core.view_objectchange", "ipam.view_ipaddress"]

    def test_every_page_renders(self):
        source = make_source(source_timezone="UTC", field_mapping={"hostname": "name"})
        job = ImportJob.objects.create(source=source, status=ImportStatusChoices.COMPLETED, created_records=1,
                                       error_details=[{"row": 2, "error": "Invalid IP address: x"}])
        ip_change("192.0.2.80/24")
        event = HistoricalIPEvent.objects.get()
        ip = IPAddress.objects.create(address="192.0.2.81/24")
        pages = [
            url("timeline"), f"{url('timeline')}?ip=192.0.2.80", f"{url('compare')}?ip=192.0.2.80",
            url("import"), url("source_support"),
            url("importsource_list"), url("importsource_add"), source.get_absolute_url(),
            url("importsource_edit", source.pk), url("importsource_changelog", source.pk),
            url("importjob_list"), job.get_absolute_url(), url("importjob_edit", job.pk),
            url("importjob_jobs", job.pk),
            url("historicalipevent_list"), event.get_absolute_url(), url("historicalipevent_changelog", event.pk),
            reverse("ipam:ipaddress_ip_history", args=[ip.pk]), ip.get_absolute_url(),
        ]
        for page in pages:
            with self.subTest(page=page):
                self.assertEqual(self.client.get(page).status_code, 200)


class DuplicateUploadWarningTests(TestCase):
    user_permissions = [
        "netbox_ip_history.view_importsource",
        "netbox_ip_history.add_historicalipevent",
        "netbox_ip_history.add_importjob",
        "netbox_ip_history.view_importjob",
    ]

    def test_second_upload_of_same_file_shows_warning(self):
        source = make_source(source_timezone="UTC")
        payload = {"source": source.pk, "format": "csv", "delimiter": ","}
        self.client.post(url("import"), {**payload, "file": SimpleUploadedFile("h.csv", CSV)})
        response = self.client.post(url("import"), {**payload, "file": SimpleUploadedFile("h.csv", CSV)}, follow=True)
        self.assertContains(response, "already imported")


class IPAddressTabScopeTests(TestCase):
    user_permissions = ["ipam.view_ipaddress", "netbox_ip_history.view_historicalipevent", "core.view_objectchange"]

    def test_tab_shows_only_the_addresses_vrf(self):
        import uuid

        from django.test import RequestFactory
        from ipam.models import VRF
        from netbox.context_managers import event_tracking

        request = RequestFactory().get("/")
        request.id, request.user = uuid.uuid4(), self.user
        vrf_a, vrf_ab = VRF.objects.create(name="VRF-A"), VRF.objects.create(name="VRF-AB")
        with event_tracking(request):
            ip = IPAddress.objects.create(address="198.51.100.77/24", vrf=vrf_a)
            IPAddress.objects.create(address="198.51.100.77/24", vrf=vrf_ab)
            IPAddress.objects.create(address="198.51.100.77/24")

        response = self.client.get(reverse("ipam:ipaddress_ip_history", args=[ip.pk]))
        self.assertEqual([e["vrf"] for e in response.context["events"]], ["VRF-A"])

        detail = self.client.get(ip.get_absolute_url())
        self.assertContains(detail, "?ip=198.51.100.77&amp;vrf=VRF-A")


class BackgroundUploadTests(TestCase):
    user_permissions = [
        "netbox_ip_history.view_importsource",
        "netbox_ip_history.add_historicalipevent",
        "netbox_ip_history.add_importjob",
    ]

    def test_queued_job_records_file_hash(self):
        import hashlib
        from unittest import mock

        from netbox_ip_history.jobs import ImportHistoryJobRunner

        source = make_source(source_timezone="UTC")
        with mock.patch.object(ImportHistoryJobRunner, "enqueue") as enqueue:
            self.client.post(
                url("import"),
                {"source": source.pk, "format": "csv", "delimiter": ",", "background": "on",
                 "file": SimpleUploadedFile("h.csv", CSV)},
            )
        job = ImportJob.objects.get()
        enqueue.assert_called_once()
        self.assertEqual(job.file_hash, hashlib.sha256(CSV).hexdigest())
        self.assertEqual(job.file_size, len(CSV))


class EventDeletionTests(TestCase):
    user_permissions = ["netbox_ip_history.view_historicalipevent", "netbox_ip_history.delete_historicalipevent"]

    def test_imported_event_can_be_deleted_in_the_ui(self):
        from netbox_ip_history.services.import_service import build_importer, run_import

        source = make_source(source_timezone="UTC")
        run_import(source, build_importer(source, CSV))
        event = HistoricalIPEvent.objects.get()
        response = self.client.post(url("historicalipevent_delete", event.pk), {"confirm": True})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(HistoricalIPEvent.objects.filter(pk=event.pk).exists())


class ExportSanitizationTests(TestCase):
    user_permissions = ["netbox_ip_history.view_historicalipevent"]

    def test_csv_export_neutralizes_spreadsheet_formulas(self):
        import csv
        import io
        from datetime import UTC, datetime

        source = make_source(source_timezone="UTC")
        payloads = {
            "hostname": "=HYPERLINK(\"http://example.com\",\"x\")",
            "owner_name": "+1+1",
            "dns_name": "-2+3",
            "description": "@SUM(1)",
            "status": "\tactive",
            "interface_name": "\reth0",
        }
        HistoricalIPEvent.objects.create(
            source=source, ip_address="198.51.100.9", event_type="imported", fingerprint="x",
            timestamp=datetime(2025, 1, 1, tzinfo=UTC), **payloads,
        )
        response = self.client.get(url("timeline"), {"ip": "198.51.100.9", "export": "csv"})
        row = next(csv.DictReader(io.StringIO(response.content.decode())))
        for field, value in payloads.items():
            with self.subTest(field=field):
                self.assertEqual(row[field], "'" + value)

        exported = self.client.get(url("timeline"), {"ip": "198.51.100.9", "export": "json"}).json()[0]
        self.assertEqual(exported["hostname"], payloads["hostname"])


class TimelineAPIFilterTests(TestCase):
    user_permissions = ["netbox_ip_history.view_historicalipevent", "core.view_objectchange"]

    def setUp(self):
        super().setUp()
        ip_change("192.0.2.70/24", user_name="alice", minutes=0)  # 2026-01-01, recorded as an event
        late = ip_change("192.0.2.70/24", action="update", user_name="bob", pre={"address": "192.0.2.70/24"},
                         post={"address": "192.0.2.70/24", "dns_name": "device-70.example.com"}, minutes=60 * 24 * 40)
        HistoricalIPEvent.objects.filter(source_record_id=str(late.pk)).delete()  # live ObjectChange only

    def api(self, **params):
        return self.client.get(reverse("plugins-api:netbox_ip_history-api:timeline"), {"ip": "192.0.2.70", **params})

    def test_entries_report_their_kind(self):
        kinds = {entry["username"]: entry["kind"] for entry in self.api().json()}
        self.assertEqual(kinds, {"alice": "event", "bob": "objectchange"})

    def test_ui_filters_are_available(self):
        def users(**params):
            return [entry["username"] for entry in self.api(**params).json()]

        self.assertEqual(users(date_from="2026-02-01"), ["bob"])
        self.assertEqual(users(date_to="2026-01-31"), ["alice"])
        self.assertEqual(users(username="ali"), ["alice"])
        self.assertEqual(users(owner="device-70"), ["bob"])
        self.assertEqual(self.api(date_from="31/01/2026").status_code, 400)

    def test_openapi_schema_documents_filters_and_kind(self):
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        patterns = [path("api/plugins/ip-history/", include("netbox_ip_history.api.urls"))]
        schema = SchemaGenerator(patterns=patterns).get_schema(request=None, public=True)
        operation = schema["paths"]["/api/plugins/ip-history/timeline/"]["get"]
        params = {p["name"] for p in operation["parameters"]}
        self.assertTrue({"ip", "vrf", "date_from", "date_to", "owner", "username", "oldest_first"} <= params)
        entry = operation["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"]
        properties = schema["components"]["schemas"][entry.rsplit("/", 1)[1]]["properties"]
        self.assertIn("kind", properties)
