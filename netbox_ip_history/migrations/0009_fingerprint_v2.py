from django.db import migrations

from netbox_ip_history.migrations._fingerprints import fingerprint_v2, recompute


def forwards(apps, schema_editor):
    recompute(apps, fingerprint_v2)


class Migration(migrations.Migration):
    """Fingerprint v2 also covers VRF, RD, MAC address, status and DNS name."""

    dependencies = [("netbox_ip_history", "0008_netbox_models")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
