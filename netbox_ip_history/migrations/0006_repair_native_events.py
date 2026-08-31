from django.db import migrations


def repair_native_events(apps, schema_editor):
    HistoricalIPEvent = apps.get_model("netbox_ip_history", "HistoricalIPEvent")
    ImportSource = apps.get_model("netbox_ip_history", "ImportSource")

    try:
        netbox_src = ImportSource.objects.filter(slug="netbox").first()
        if not netbox_src:
            return
    except Exception:
        return

    try:
        from netbox_ip_history.services.timeline import extract_netbox_change_details
        for event in HistoricalIPEvent.objects.filter(source=netbox_src):
            raw = event.raw_data or {}
            payloads = [raw.get("postchange_data") or {}, raw.get("prechange_data") or {}]
            payload = next((p for p in payloads if isinstance(p, dict) and p), {})
            if payload:
                details = extract_netbox_change_details(payload)
                if details.get("host_name"):
                    event.owner_name = details["host_name"]
                if details.get("interface_name"):
                    event.interface_name = details["interface_name"]
                if details.get("dns_name"):
                    event.dns_name = details["dns_name"]
                if details.get("dns_name") or details.get("host_name"):
                    event.hostname = details["dns_name"] or details["host_name"]
                event.save(update_fields=["owner_name", "interface_name", "dns_name", "hostname"])
            elif event.dns_name and event.owner_name and event.owner_name != event.dns_name:
                event.owner_name = event.dns_name
                event.hostname = event.dns_name
                event.save(update_fields=["owner_name", "hostname"])
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_ip_history", "0005_seed_support_matrix_sources"),
    ]

    operations = [
        migrations.RunPython(repair_native_events, reverse_code=migrations.RunPython.noop),
    ]
