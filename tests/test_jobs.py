from django.contrib.auth import get_user_model
from django.test import TestCase

from netbox_ip_history.choices import ImportStatusChoices
from netbox_ip_history.jobs import ImportHistoryJobRunner
from netbox_ip_history.models import ImportJob

from .helpers import make_source

CSV = b"timestamp,ip,event_type\n2026-01-01T00:00:00+00:00,192.0.2.70,created\n2026-01-02T00:00:00+00:00,bad,created\n"


class BackgroundImportTests(TestCase):
    def test_pending_job_is_completed_by_runner(self):
        user = get_user_model().objects.create_user(username="operator")
        job = ImportJob.objects.create(source=make_source(source_timezone="UTC"), status=ImportStatusChoices.PENDING)
        core_job = ImportHistoryJobRunner.enqueue(instance=job, user=user, immediate=True, data=CSV, format="csv")
        job.refresh_from_db()
        self.assertEqual(job.status, ImportStatusChoices.COMPLETED)
        self.assertEqual((job.created_records, job.error_records), (1, 1))
        core_job.refresh_from_db()
        self.assertEqual(core_job.status, "completed")
        self.assertEqual(core_job.data["created"], 1)
        self.assertIn(core_job, job.jobs.all())
