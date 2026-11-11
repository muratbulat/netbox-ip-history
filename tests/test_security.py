"""Regression tests for import-job deletion permissions (H1) and native raw_data visibility (H2)."""

from core.models import ObjectType
from django.test import override_settings
from django.urls import reverse
from users.models import ObjectPermission
from utilities.testing import APITestCase, TestCase

from netbox_ip_history.models import HistoricalIPEvent, ImportJob
from netbox_ip_history.services.import_service import build_importer, run_import

from .helpers import ip_change, make_source

CSV = (
    b"ip,timestamp,event_type,vrf\n"
    b"192.0.2.1,2025-01-01 10:00,create,BLUE\n"
    b"192.0.2.2,2025-01-01 10:00,create,RED\n"
)
SECRET = "changelog-only-comment-7f3a"


def url(name, *args):
    return reverse(f"plugins:netbox_ip_history:{name}", args=args)


def api_url(name, pk):
    return reverse(f"plugins-api:netbox_ip_history-api:{name}-detail", args=[pk])


class GrantMixin:
    def grant(self, model, actions, constraints=None, app_label="netbox_ip_history"):
        permission = ObjectPermission.objects.create(
            name=f"{app_label}-{model}-{'-'.join(actions)}", actions=actions, constraints=constraints
        )
        permission.object_types.add(ObjectType.objects.get(app_label=app_label, model=model))
        permission.users.add(self.user)

    def make_job(self):
        source = make_source(source_timezone="UTC")
        _, job = run_import(source, build_importer(source, CSV))
        return job

    def assert_job_intact(self, job):
        self.assertTrue(ImportJob.objects.filter(pk=job.pk).exists())
        self.assertEqual(HistoricalIPEvent.objects.filter(import_job=job).count(), 2)


@override_settings(EXEMPT_VIEW_PERMISSIONS=[])
class ImportJobDeleteUITests(GrantMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.job = self.make_job()
        self.grant("importjob", ["view", "delete"])

    def test_delete_refused_without_event_delete_permission(self):
        response = self.client.post(url("importjob_delete", self.job.pk), {"confirm": True}, follow=True)
        self.assert_job_intact(self.job)
        self.assertContains(response, "nothing was deleted")

    def test_delete_refused_when_events_fall_outside_delete_constraints(self):
        self.grant("historicalipevent", ["delete"], {"vrf_name": "BLUE"})
        self.client.post(url("importjob_delete", self.job.pk), {"confirm": True})
        self.assert_job_intact(self.job)

    def test_bulk_delete_refused_without_event_delete_permission(self):
        self.client.post(url("importjob_bulk_delete"), {"pk": [self.job.pk], "confirm": True, "_confirm": True})
        self.assert_job_intact(self.job)

    def test_delete_allowed_when_every_event_is_deletable(self):
        self.grant("historicalipevent", ["delete"])
        self.client.post(url("importjob_delete", self.job.pk), {"confirm": True})
        self.assertFalse(ImportJob.objects.filter(pk=self.job.pk).exists())
        self.assertFalse(HistoricalIPEvent.objects.exists())

    def test_job_without_events_needs_only_job_permission(self):
        HistoricalIPEvent.objects.filter(import_job=self.job).delete()
        self.client.post(url("importjob_delete", self.job.pk), {"confirm": True})
        self.assertFalse(ImportJob.objects.filter(pk=self.job.pk).exists())

    def test_delete_outside_a_request_is_not_restricted(self):
        self.job.delete()  # e.g. shell or management command: no acting user
        self.assertFalse(HistoricalIPEvent.objects.exists())


@override_settings(EXEMPT_VIEW_PERMISSIONS=[])
class ImportJobDeleteAPITests(GrantMixin, APITestCase):
    user_permissions = ()

    def setUp(self):
        super().setUp()
        self.job = self.make_job()
        self.grant("importjob", ["view", "delete"])

    def test_api_delete_refused_without_event_delete_permission(self):
        response = self.client.delete(api_url("importjob", self.job.pk), **self.header)
        self.assertEqual(response.status_code, 400)
        self.assertIn("nothing was deleted", response.json()["detail"])
        self.assert_job_intact(self.job)

    def test_api_delete_allowed_when_every_event_is_deletable(self):
        self.grant("historicalipevent", ["delete"])
        response = self.client.delete(api_url("importjob", self.job.pk), **self.header)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(HistoricalIPEvent.objects.exists())


class RawDataFixtureMixin:
    def make_events(self):
        ip_change("192.0.2.80/24", post={"address": "192.0.2.80/24", "custom_fields": {"note": SECRET}})
        self.native = HistoricalIPEvent.objects.get(ip_address="192.0.2.80")
        self.imported = HistoricalIPEvent.objects.filter(import_job=self.make_job()).first()


@override_settings(EXEMPT_VIEW_PERMISSIONS=[])
class NativeRawDataUITests(RawDataFixtureMixin, GrantMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.make_events()
        self.add_permissions("netbox_ip_history.view_historicalipevent")

    def test_native_raw_data_hidden_without_changelog_permission(self):
        response = self.client.get(self.native.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, SECRET)
        self.assertNotContains(response, "begin SourceRecordPanel")

    def test_native_raw_data_shown_with_changelog_permission(self):
        self.add_permissions("core.view_objectchange")
        self.assertContains(self.client.get(self.native.get_absolute_url()), SECRET)

    def test_imported_raw_data_needs_no_changelog_permission(self):
        self.assertContains(self.client.get(self.imported.get_absolute_url()), "begin SourceRecordPanel")


@override_settings(EXEMPT_VIEW_PERMISSIONS=[])
class NativeRawDataAPITests(RawDataFixtureMixin, GrantMixin, APITestCase):
    user_permissions = ("netbox_ip_history.view_historicalipevent",)

    def setUp(self):
        super().setUp()
        self.make_events()

    def get(self, event):
        response = self.client.get(api_url("historicalipevent", event.pk), **self.header)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_native_raw_data_withheld_without_changelog_permission(self):
        self.assertIsNone(self.get(self.native)["raw_data"])
        list_response = self.client.get(
            reverse("plugins-api:netbox_ip_history-api:historicalipevent-list"), **self.header
        )
        self.assertNotIn(SECRET, list_response.content.decode())

    def test_native_raw_data_returned_with_changelog_permission(self):
        self.add_permissions("core.view_objectchange")
        self.assertEqual(self.get(self.native)["raw_data"]["postchange_data"]["custom_fields"]["note"], SECRET)

    def test_imported_raw_data_needs_no_changelog_permission(self):
        self.assertIn("ip", self.get(self.imported)["raw_data"])
