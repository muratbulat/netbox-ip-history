import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Schema as of 0.3.x (migrations 0001-0007), squashed. Existing installs skip it."""

    replaces = [
        ("netbox_ip_history", "0001_initial"),
        ("netbox_ip_history", "0002_source_profiles"),
        ("netbox_ip_history", "0003_alter_historicalipevent_options_and_more"),
        ("netbox_ip_history", "0004_unify_gestioip_sources"),
        ("netbox_ip_history", "0005_seed_support_matrix_sources"),
        ("netbox_ip_history", "0006_repair_native_events"),
        ("netbox_ip_history", "0007_sync_model_metadata_indexes"),
    ]

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ipam", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(unique=True)),
                ("source_type", models.CharField(max_length=20)),
                ("enabled", models.BooleanField(default=True)),
                ("description", models.TextField(blank=True)),
                ("source_timezone", models.CharField(blank=True, max_length=64)),
                ("field_mapping", models.JSONField(blank=True, default=dict)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("last_updated", models.DateTimeField(auto_now=True)),
                ("support_level", models.CharField(blank=True, max_length=20)),
                ("capabilities", models.JSONField(blank=True, default=list)),
                ("inspection", models.JSONField(blank=True, default=dict)),
                ("source_priority", models.PositiveIntegerField(default=100)),
                ("authority", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="ImportJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started", models.DateTimeField(auto_now_add=True)),
                ("completed", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(default="running", max_length=20)),
                ("filename", models.CharField(blank=True, max_length=255)),
                ("file_hash", models.CharField(blank=True, max_length=64)),
                ("file_size", models.PositiveBigIntegerField(blank=True, null=True)),
                ("import_mode", models.CharField(default="history_only", max_length=30)),
                ("total_records", models.PositiveIntegerField(default=0)),
                ("processed_records", models.PositiveIntegerField(default=0)),
                ("created_records", models.PositiveIntegerField(default=0)),
                ("updated_records", models.PositiveIntegerField(default=0)),
                ("skipped_records", models.PositiveIntegerField(default=0)),
                ("duplicate_records", models.PositiveIntegerField(default=0)),
                ("conflict_records", models.PositiveIntegerField(default=0)),
                ("error_records", models.PositiveIntegerField(default=0)),
                ("dry_run", models.BooleanField(default=False)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("error_details", models.JSONField(blank=True, default=list)),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="jobs",
                        to="netbox_ip_history.importsource",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-started",)},
        ),
        migrations.CreateModel(
            name="HistoricalIPEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField()),
                ("ip_address", models.GenericIPAddressField()),
                ("prefix_length", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("vrf_name", models.CharField(blank=True, max_length=255)),
                ("vrf_rd", models.CharField(blank=True, max_length=255)),
                ("source_scope_identifier", models.CharField(blank=True, max_length=255)),
                ("tenant_name", models.CharField(blank=True, max_length=255)),
                ("event_type", models.CharField(max_length=30)),
                ("source_record_id", models.CharField(blank=True, max_length=255)),
                ("source_event_type", models.CharField(blank=True, max_length=255)),
                ("source_username", models.CharField(blank=True, max_length=255)),
                ("hostname", models.CharField(blank=True, max_length=255)),
                ("dns_name", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("owner_type", models.CharField(blank=True, max_length=64)),
                ("owner_name", models.CharField(blank=True, max_length=255)),
                ("interface_name", models.CharField(blank=True, max_length=255)),
                ("mac_address", models.CharField(blank=True, max_length=64)),
                ("device_name", models.CharField(blank=True, max_length=255)),
                ("virtual_machine_name", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(blank=True, max_length=255)),
                ("location", models.CharField(blank=True, max_length=255)),
                ("site", models.CharField(blank=True, max_length=255)),
                ("role", models.CharField(blank=True, max_length=255)),
                ("tags_snapshot", models.JSONField(blank=True, default=list)),
                ("custom_fields_snapshot", models.JSONField(blank=True, default=dict)),
                ("raw_data", models.JSONField(default=dict)),
                ("fingerprint", models.CharField(max_length=64, unique=True)),
                (
                    "import_job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="netbox_ip_history.importjob",
                    ),
                ),
                (
                    "related_netbox_ip",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="ipam.ipaddress"
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="events",
                        to="netbox_ip_history.importsource",
                    ),
                ),
            ],
            options={
                "ordering": ("-timestamp", "-id"),
                "indexes": [
                    models.Index(fields=["ip_address", "-timestamp"], name="netbox_ip_h_ip_addr_883ca1_idx"),
                    models.Index(fields=["source", "ip_address"], name="netbox_ip_h_source__577fd7_idx"),
                    models.Index(fields=["event_type", "-timestamp"], name="netbox_ip_h_event_t_7b92da_idx"),
                    models.Index(fields=["vrf_name", "vrf_rd", "ip_address"], name="netbox_ip_h_vrf_nam_068191_idx"),
                    models.Index(fields=["import_job", "ip_address"], name="netbox_ip_h_import__1a5e0c_idx"),
                ],
            },
        ),
    ]
