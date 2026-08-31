from django.db import migrations

MATRIX_SOURCES = [
    {
        "name": "GestióIP",
        "slug": "gestioip",
        "source_type": "gestioip",
        "description": "GestioIP inventory lists and audit logs",
        "support_level": "EXPORT",
    },
    {
        "name": "phpIPAM",
        "slug": "phpipam",
        "source_type": "phpipam",
        "description": "phpIPAM CSV/JSON exports and API sync",
        "support_level": "EXPORT",
    },
    {
        "name": "RackTables",
        "slug": "racktables",
        "source_type": "racktables",
        "description": "RackTables database and inventory export",
        "support_level": "EXPORT",
    },
    {
        "name": "GLPI",
        "slug": "glpi",
        "source_type": "glpi",
        "description": "GLPI network equipment and IP history",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "Device42",
        "slug": "device42",
        "source_type": "device42",
        "description": "Device42 IPAM and autodiscovery history",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "Infoblox NIOS / DDI",
        "slug": "infoblox",
        "source_type": "infoblox",
        "description": "Infoblox NIOS CSV and API exports",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "BlueCat Address Manager",
        "slug": "bluecat",
        "source_type": "bluecat",
        "description": "BlueCat BAM export files",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "BlueCat Micetro / Men&Mice",
        "slug": "micetro",
        "source_type": "micetro",
        "description": "Micetro by Men&Mice IPAM exports",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "EfficientIP SOLIDserver",
        "slug": "efficientip",
        "source_type": "efficientip",
        "description": "EfficientIP SOLIDserver history exports",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "NIPAP",
        "slug": "nipap",
        "source_type": "nipap",
        "description": "NIPAP database and CSV exports",
        "support_level": "EXPORT",
    },
    {
        "name": "TeemIP / iTop",
        "slug": "teemip",
        "source_type": "teemip",
        "description": "Combodo TeemIP / iTop IPAM history",
        "support_level": "EXPORT",
    },
    {
        "name": "SolarWinds IPAM",
        "slug": "solarwinds",
        "source_type": "solarwinds",
        "description": "SolarWinds IP Address Manager exports",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "ManageEngine OpUtils",
        "slug": "manageengine",
        "source_type": "manageengine",
        "description": "ManageEngine OpUtils IP history",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "Microsoft Windows Server IPAM",
        "slug": "microsoft-ipam",
        "source_type": "microsoft_ipam",
        "description": "Windows Server DHCP / IPAM exports",
        "support_level": "EXPORT",
    },
    {
        "name": "Another NetBox instance",
        "slug": "netbox-external",
        "source_type": "netbox",
        "description": "External NetBox instance exports",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "Nautobot",
        "slug": "nautobot",
        "source_type": "nautobot",
        "description": "Nautobot IPAM exports and history",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "Ralph",
        "slug": "ralph",
        "source_type": "ralph",
        "description": "Ralph Asset Management and IP history",
        "support_level": "EXPERIMENTAL",
    },
    {
        "name": "Generic CSV / TSV",
        "slug": "generic-csv",
        "source_type": "generic_csv",
        "description": "Generic delimited spreadsheet export",
        "support_level": "EXPORT",
    },
    {
        "name": "Generic JSON / JSONL",
        "slug": "generic-json",
        "source_type": "generic_json",
        "description": "Generic structured JSON and JSON Lines",
        "support_level": "EXPORT",
    },
    {
        "name": "Generic SQL Export",
        "slug": "generic-sql",
        "source_type": "generic_sql",
        "description": "Generic SQL dump / tabular export",
        "support_level": "EXPERIMENTAL",
    },
]


def seed_support_matrix_sources(apps, schema_editor):
    ImportSource = apps.get_model("netbox_ip_history", "ImportSource")

    for item in MATRIX_SOURCES:
        # Check by slug or name
        src = ImportSource.objects.filter(slug=item["slug"]).first()
        if not src:
            src = ImportSource.objects.filter(name=item["name"]).first()
        if not src:
            ImportSource.objects.create(
                name=item["name"],
                slug=item["slug"],
                source_type=item["source_type"],
                description=item["description"],
                support_level=item.get("support_level", "EXPORT"),
                enabled=True,
            )
        else:
            # Update existing to ensure enabled and valid metadata
            src.enabled = True
            if not src.source_type:
                src.source_type = item["source_type"]
            src.save()


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_ip_history", "0004_unify_gestioip_sources"),
    ]

    operations = [
        migrations.RunPython(seed_support_matrix_sources, reverse_noop),
    ]
