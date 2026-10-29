from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from users.models import ObjectPermission
from utilities.testing import TestCase

from netbox_ip_history.choices import ImportStatusChoices
from netbox_ip_history.models import HistoricalIPEvent, ImportJob
from netbox_ip_history.services.import_service import build_importer, run_import

from .helpers import make_source

CSV = (
    b"ip,timestamp,event_type,vrf\n"
    b"192.0.2.1,2025-01-01 10:00,create,BLUE\n"
    b"192.0.2.2,2025-01-01 10:00,create,RED\n"
)


class ObjectPermissionTests(TestCase):
    def setUp(self):
        super().setUp()
        self.source = make_source(source_timezone="UTC")

    def grant(self, model, actions, constraints=None):
        from core.models import ObjectType

        permission = ObjectPermission.objects.create(
            name=f"{model}-{'-'.join(actions)}", actions=actions, constraints=constraints
        )
        permission.object_types.add(ObjectType.objects.get(app_label="netbox_ip_history", model=model))
        permission.users.add(self.user)

    def test_rollback_refuses_events_outside_delete_constraints(self):
        _, job = run_import(self.source, build_importer(self.source, CSV))
        self.grant("importjob", ["view", "change"])
        self.grant("historicalipevent", ["delete"], {"vrf_name": "BLUE"})

        response = self.client.post(reverse("plugins:netbox_ip_history:importjob_rollback", args=[job.pk]), follow=True)

        job.refresh_from_db()
        self.assertEqual(job.status, ImportStatusChoices.COMPLETED)
        self.assertEqual(HistoricalIPEvent.objects.filter(import_job=job).count(), 2)
        self.assertContains(response, "not permitted")

    def test_rollback_allowed_when_all_events_are_deletable(self):
        _, job = run_import(self.source, build_importer(self.source, CSV))
        self.grant("importjob", ["view", "change"])
        self.grant("historicalipevent", ["delete"])
        self.client.post(reverse("plugins:netbox_ip_history:importjob_rollback", args=[job.pk]))
        job.refresh_from_db()
        self.assertEqual(job.status, ImportStatusChoices.ROLLED_BACK)

    def test_import_refuses_rows_outside_add_constraints(self):
        self.grant("importsource", ["view"])
        self.grant("importjob", ["add", "view"])
        self.grant("historicalipevent", ["add"], {"vrf_name": "BLUE"})

        response = self.client.post(
            reverse("plugins:netbox_ip_history:import"),
            {"source": self.source.pk, "format": "csv", "delimiter": ",", "file": SimpleUploadedFile("h.csv", CSV)},
        )

        self.assertContains(response, "not permitted")
        self.assertFalse(HistoricalIPEvent.objects.exists())
        self.assertEqual(ImportJob.objects.get().status, ImportStatusChoices.FAILED)

    def test_import_within_add_constraints_succeeds(self):
        self.grant("importsource", ["view"])
        self.grant("importjob", ["add", "view"])
        self.grant("historicalipevent", ["add"], {"vrf_name": "BLUE"})
        blue_only = CSV.rsplit(b"\n", 2)[0] + b"\n"
        self.client.post(
            reverse("plugins:netbox_ip_history:import"),
            {"source": self.source.pk, "format": "csv", "delimiter": ",",
             "file": SimpleUploadedFile("h.csv", blue_only)},
        )
        self.assertEqual(HistoricalIPEvent.objects.count(), 1)
