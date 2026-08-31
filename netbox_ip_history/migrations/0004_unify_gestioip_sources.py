from django.db import migrations


def unify_gestioip_sources(apps, schema_editor):
    ImportSource = apps.get_model("netbox_ip_history", "ImportSource")
    HistoricalIPEvent = apps.get_model("netbox_ip_history", "HistoricalIPEvent")
    ImportJob = apps.get_model("netbox_ip_history", "ImportJob")

    # 1. Find all GestioIP sources
    gestio_sources = list(
        ImportSource.objects.filter(source_type="gestioip").order_by("id")
    )
    if not gestio_sources:
        gestio_sources = list(
            ImportSource.objects.filter(name__icontains="gestio").order_by("id")
        )

    if gestio_sources:
        # Prefer the Production one if present, otherwise the first one
        primary_src = next((s for s in gestio_sources if "production" in s.name.lower()), gestio_sources[0])
        primary_src.name = "GestióIP"
        primary_src.slug = "gestioip"
        primary_src.source_type = "gestioip"
        primary_src.enabled = True
        primary_src.save()

        # Re-point all other GestioIP sources to primary_src and remove duplicates
        for other in gestio_sources:
            if other.pk != primary_src.pk:
                HistoricalIPEvent.objects.filter(source=other).update(source=primary_src)
                ImportJob.objects.filter(source=other).update(source=primary_src)
                other.delete()

    # 2. Clean up old demo/test sources if present
    demo_names = ["Q3 Network Audit CSV", "NetBox SSoT Sync", "q3-network-audit-csv", "netbox-ssot-sync"]
    for demo in ImportSource.objects.filter(name__in=demo_names):
        HistoricalIPEvent.objects.filter(source=demo).delete()
        ImportJob.objects.filter(source=demo).delete()
        demo.delete()


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_ip_history", "0003_alter_historicalipevent_options_and_more"),
    ]

    operations = [
        migrations.RunPython(unify_gestioip_sources, reverse_noop),
    ]
