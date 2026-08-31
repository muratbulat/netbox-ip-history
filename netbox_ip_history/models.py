try:
    from django.conf import settings
    from django.db import models
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False
    settings = None
    models = None

try:
    from netbox.models import RestrictedQuerySet
except ImportError:
    try:
        from utilities.querysets import RestrictedQuerySet
    except ImportError:
        RestrictedQuerySet = None

from .choices import EventType, ImportMode, JobStatus, SourceType

if HAS_DJANGO:
    class ImportSource(models.Model):
        name = models.CharField(max_length=100, unique=True)
        slug = models.SlugField(unique=True)
        source_type = models.CharField(max_length=20, choices=SourceType.choices)
        enabled = models.BooleanField(default=True)
        description = models.TextField(blank=True)
        source_timezone = models.CharField(max_length=64, blank=True)
        field_mapping = models.JSONField(default=dict, blank=True)
        support_level = models.CharField(max_length=20, blank=True)
        capabilities = models.JSONField(default=list, blank=True)
        inspection = models.JSONField(default=dict, blank=True)
        source_priority = models.PositiveIntegerField(default=100)
        authority = models.JSONField(default=dict, blank=True)
        created = models.DateTimeField(auto_now_add=True)
        last_updated = models.DateTimeField(auto_now=True)

        objects = RestrictedQuerySet.as_manager() if RestrictedQuerySet else models.Manager()

        class Meta:
            ordering = ("name",)

        def __str__(self):
            return self.name

        def get_absolute_url(self):
            try:
                from django.urls import reverse
                return reverse("plugins:netbox_ip_history:source_support")
            except Exception:
                return "/plugins/ip-history/sources/support/"

    class ImportJob(models.Model):
        source = models.ForeignKey(ImportSource, on_delete=models.PROTECT, related_name="jobs")
        started = models.DateTimeField(auto_now_add=True)
        completed = models.DateTimeField(null=True, blank=True)
        status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.RUNNING)
        user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
        filename = models.CharField(max_length=255, blank=True)
        file_hash = models.CharField(max_length=64, blank=True)
        file_size = models.PositiveBigIntegerField(null=True, blank=True)
        import_mode = models.CharField(max_length=30, choices=ImportMode.choices, default=ImportMode.HISTORY_ONLY)
        total_records = models.PositiveIntegerField(default=0)
        processed_records = models.PositiveIntegerField(default=0)
        created_records = models.PositiveIntegerField(default=0)
        updated_records = models.PositiveIntegerField(default=0)
        skipped_records = models.PositiveIntegerField(default=0)
        duplicate_records = models.PositiveIntegerField(default=0)
        conflict_records = models.PositiveIntegerField(default=0)
        error_records = models.PositiveIntegerField(default=0)
        dry_run = models.BooleanField(default=False)
        summary = models.JSONField(default=dict, blank=True)
        error_details = models.JSONField(default=list, blank=True)

        objects = RestrictedQuerySet.as_manager() if RestrictedQuerySet else models.Manager()

        class Meta:
            ordering = ("-started",)

        def get_absolute_url(self):
            try:
                from django.urls import reverse
                if self.pk:
                    return reverse("plugins:netbox_ip_history:import_job", kwargs={"pk": self.pk})
                return reverse("plugins:netbox_ip_history:import_jobs")
            except Exception:
                if self.pk:
                    return f"/plugins/ip-history/import-jobs/{self.pk}/"
                return "/plugins/ip-history/import-jobs/"

    class HistoricalIPEvent(models.Model):
        timestamp = models.DateTimeField()
        ip_address = models.GenericIPAddressField()
        prefix_length = models.PositiveSmallIntegerField(null=True, blank=True)
        vrf_name = models.CharField(max_length=255, blank=True)
        vrf_rd = models.CharField(max_length=255, blank=True)
        source_scope_identifier = models.CharField(max_length=255, blank=True)
        tenant_name = models.CharField(max_length=255, blank=True)
        event_type = models.CharField(max_length=30, choices=EventType.choices)
        source = models.ForeignKey(ImportSource, on_delete=models.PROTECT, related_name="events")
        source_record_id = models.CharField(max_length=255, blank=True)
        source_event_type = models.CharField(max_length=255, blank=True)
        source_username = models.CharField(max_length=255, blank=True)
        hostname = models.CharField(max_length=255, blank=True)
        dns_name = models.CharField(max_length=255, blank=True)
        description = models.TextField(blank=True)
        owner_type = models.CharField(max_length=64, blank=True)
        owner_name = models.CharField(max_length=255, blank=True)
        interface_name = models.CharField(max_length=255, blank=True)
        mac_address = models.CharField(max_length=64, blank=True)
        device_name = models.CharField(max_length=255, blank=True)
        virtual_machine_name = models.CharField(max_length=255, blank=True)
        status = models.CharField(max_length=255, blank=True)
        location = models.CharField(max_length=255, blank=True)
        site = models.CharField(max_length=255, blank=True)
        role = models.CharField(max_length=255, blank=True)
        tags_snapshot = models.JSONField(default=list, blank=True)
        custom_fields_snapshot = models.JSONField(default=dict, blank=True)
        raw_data = models.JSONField(default=dict)
        fingerprint = models.CharField(max_length=64, unique=True)
        import_job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="events")
        related_netbox_ip = models.ForeignKey("ipam.IPAddress", null=True, blank=True, on_delete=models.SET_NULL)

        objects = RestrictedQuerySet.as_manager() if RestrictedQuerySet else models.Manager()

        class Meta:
            ordering = ("-timestamp", "-id")
            indexes = [
                models.Index(fields=("ip_address", "-timestamp")),
                models.Index(fields=("source", "ip_address")),
                models.Index(fields=("event_type", "-timestamp")),
                models.Index(fields=("vrf_name", "vrf_rd", "ip_address")),
                models.Index(fields=("import_job", "ip_address")),
            ]

        def get_absolute_url(self):
            try:
                from django.urls import reverse
                return reverse("plugins:netbox_ip_history:history") + f"?ip={self.ip_address}"
            except Exception:
                return f"/plugins/ip-history/?ip={self.ip_address}"

else:
    class ImportSource:
        def get_absolute_url(self):
            return "/plugins/ip-history/sources/support/"

    class ImportJob:
        def get_absolute_url(self):
            return "/plugins/ip-history/import-jobs/"

    class HistoricalIPEvent:
        def get_absolute_url(self):
            return "/plugins/ip-history/?ip="
