from django.db import migrations

NATIVE_SLUG = "netbox"


def forwards(apps, schema_editor):
    """
    Map source types left by pre-1.0 versions onto current ones:
    - generic_sql (never implemented, no longer a choice) -> other
    - "netbox"-typed sources other than the native one were external NetBox exports; as
      "netbox" they were hidden from the import form and treated as native history.
    """
    ImportSource = apps.get_model("netbox_ip_history", "ImportSource")
    ImportSource.objects.filter(source_type="generic_sql").update(source_type="other")
    ImportSource.objects.filter(source_type="netbox").exclude(slug=NATIVE_SLUG).update(source_type="netbox_export")


class Migration(migrations.Migration):
    dependencies = [("netbox_ip_history", "0010_snapshot_fingerprint_v3")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
