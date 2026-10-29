from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from utilities.testing import TestCase

from netbox_ip_history.models import ImportSource

from .helpers import make_source


class ImportSourceValidationTests(TestCase):
    user_permissions = [
        "netbox_ip_history.view_importsource",
        "netbox_ip_history.add_importsource",
        "netbox_ip_history.add_historicalipevent",
        "netbox_ip_history.add_importjob",
    ]

    def source(self, **fields):
        return ImportSource(name="src", slug="src", source_type="generic_csv", **fields)

    def test_unknown_timezone_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.source(source_timezone="Not/AZone").full_clean()
        self.assertIn("source_timezone", ctx.exception.message_dict)
        self.source(source_timezone="Europe/Istanbul").full_clean()

    def test_field_mapping_must_map_known_fields_to_column_names(self):
        for mapping in ([1, 2], "hostname", {"hostname": 5}, {"no_such_field": "col"}, {"hostname": ""}):
            with self.subTest(mapping=mapping), self.assertRaises(ValidationError) as ctx:
                self.source(field_mapping=mapping).full_clean()
            self.assertIn("field_mapping", ctx.exception.message_dict)
        self.source(field_mapping={"hostname": "Server Name", "ip_address": "addr"}).full_clean()

    def test_form_and_api_reject_invalid_configuration(self):
        response = self.client.post(
            reverse("plugins:netbox_ip_history:importsource_add"),
            {"name": "src", "slug": "src", "source_type": "generic_csv", "source_timezone": "Not/AZone",
             "field_mapping": "[1, 2]", "source_priority": 100},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unknown timezone")
        self.assertFalse(ImportSource.objects.exists())

        api = self.client.post(
            reverse("plugins-api:netbox_ip_history-api:importsource-list"),
            {"name": "src", "slug": "src", "source_type": "generic_csv", "field_mapping": [1, 2]},
            content_type="application/json",
        )
        self.assertEqual(api.status_code, 400)
        self.assertIn("field_mapping", api.json())

    def test_legacy_invalid_mapping_fails_the_import_cleanly(self):
        source = make_source(source_timezone="UTC")
        ImportSource.objects.filter(pk=source.pk).update(field_mapping=[1, 2])  # saved before validation existed
        response = self.client.post(
            reverse("plugins:netbox_ip_history:import"),
            {"source": source.pk, "format": "csv", "delimiter": ",",
             "file": SimpleUploadedFile("h.csv", b"ip\n192.0.2.1\n")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import failed")


class NativeSourceReservationTests(TestCase):
    user_permissions = ["netbox_ip_history.add_importsource", "netbox_ip_history.change_importsource"]

    def test_netbox_type_and_slug_are_reserved_for_the_native_source(self):
        cases = (
            {"slug": "other-netbox", "source_type": "netbox"},
            {"slug": "netbox", "source_type": "generic_csv"},
        )
        for fields in cases:
            with self.subTest(**fields), self.assertRaises(ValidationError):
                ImportSource(name=fields["slug"], **fields).full_clean()
        ImportSource(name="NetBox", slug="netbox", source_type="netbox").full_clean()

        api = self.client.post(
            reverse("plugins-api:netbox_ip_history-api:importsource-list"),
            {"name": "remote", "slug": "remote", "source_type": "netbox"},
            content_type="application/json",
        )
        self.assertEqual(api.status_code, 400)

    def test_native_source_lookup_uses_slug_and_type(self):
        from django.core.exceptions import ImproperlyConfigured

        from netbox_ip_history.signals import get_native_source

        ImportSource.objects.create(name="Remote NetBox", slug="netbox-external", source_type="netbox_export")
        native = get_native_source()
        self.assertEqual((native.slug, native.source_type), ("netbox", "netbox"))
        ImportSource.objects.filter(pk=native.pk).update(source_type="generic_csv")
        with self.assertRaises(ImproperlyConfigured):
            get_native_source()


class LegacySourceMigrationTests(TestCase):
    def test_0011_maps_legacy_source_types(self):
        import importlib

        from django.apps import apps

        migration = importlib.import_module("netbox_ip_history.migrations.0011_legacy_source_types")
        sql = make_source("generic-sql", "generic_csv")
        external = make_source("netbox-external", "generic_csv")
        native = make_source("netbox", "netbox")
        ImportSource.objects.filter(pk=sql.pk).update(source_type="generic_sql")
        ImportSource.objects.filter(pk=external.pk).update(source_type="netbox")

        migration.forwards(apps, None)

        types = dict(ImportSource.objects.values_list("slug", "source_type"))
        self.assertEqual(types, {"generic-sql": "other", "netbox-external": "netbox_export", "netbox": "netbox"})
        self.assertEqual(ImportSource.objects.get(pk=native.pk).source_type, "netbox")
