from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from netbox.models import NetBoxModel
from netbox.models.features import JobsMixin

from .choices import EventTypeChoices, ImportModeChoices, ImportStatusChoices, SourceTypeChoices

__all__ = ("HistoricalIPEvent", "ImportJob", "ImportSource")

#: Canonical scope label for addresses outside any VRF.
GLOBAL_VRF = "Global"


class ImportSource(NetBoxModel):
    """A system of record that IP history is imported from (or NetBox itself)."""

    name = models.CharField(verbose_name=_("name"), max_length=100, unique=True)
    slug = models.SlugField(verbose_name=_("slug"), max_length=100, unique=True)
    source_type = models.CharField(verbose_name=_("source type"), max_length=20, choices=SourceTypeChoices)
    enabled = models.BooleanField(verbose_name=_("enabled"), default=True)
    description = models.TextField(verbose_name=_("description"), blank=True)
    source_timezone = models.CharField(
        verbose_name=_("source timezone"),
        max_length=64,
        blank=True,
        help_text=_("IANA timezone applied to naive timestamps in imported files (e.g. Europe/Istanbul)."),
    )
    field_mapping = models.JSONField(
        verbose_name=_("field mapping"),
        default=dict,
        blank=True,
        help_text=_("Optional mapping of normalized field name to source column name."),
    )
    source_priority = models.PositiveIntegerField(verbose_name=_("priority"), default=100)

    clone_fields = ("source_type", "enabled", "source_timezone", "field_mapping", "source_priority")

    class Meta:
        ordering = ("name",)
        verbose_name = _("import source")
        verbose_name_plural = _("import sources")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_ip_history:importsource", args=[self.pk])

    def clean(self):
        super().clean()
        errors = {}
        if self.source_timezone:
            try:
                ZoneInfo(self.source_timezone)
            except (ZoneInfoNotFoundError, ValueError):
                errors["source_timezone"] = _(
                    "Unknown timezone {name!r}; use an IANA name such as Europe/Istanbul."
                ).format(name=self.source_timezone)
        if mapping_error := self._field_mapping_error():
            errors["field_mapping"] = mapping_error
        if errors:
            raise ValidationError(errors)

    def _field_mapping_error(self):
        from .importers.base import DEFAULT_ALIASES  # importers import models; avoid the import cycle

        mapping = self.field_mapping
        if mapping in (None, ""):
            return None
        if not isinstance(mapping, dict):
            return _("Must be a JSON object mapping field names to source column names.")
        unknown = sorted(str(key) for key in mapping if key not in DEFAULT_ALIASES)
        if unknown:
            return _("Unknown field(s): {unknown}. Valid fields: {valid}.").format(
                unknown=", ".join(unknown), valid=", ".join(sorted(DEFAULT_ALIASES))
            )
        if not all(isinstance(column, str) and column.strip() for column in mapping.values()):
            return _("Every field must map to a non-empty source column name.")
        return None


class ImportJob(JobsMixin, NetBoxModel):
    """One import of a file into HistoricalIPEvent rows; the unit of rollback."""

    source = models.ForeignKey(
        to=ImportSource, on_delete=models.PROTECT, related_name="jobs", verbose_name=_("source")
    )
    started = models.DateTimeField(verbose_name=_("started"), auto_now_add=True)
    completed = models.DateTimeField(verbose_name=_("completed"), null=True, blank=True)
    status = models.CharField(
        verbose_name=_("status"), max_length=20, choices=ImportStatusChoices, default=ImportStatusChoices.PENDING
    )
    user = models.ForeignKey(
        to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    filename = models.CharField(verbose_name=_("filename"), max_length=255, blank=True)
    file_hash = models.CharField(verbose_name=_("SHA-256"), max_length=64, blank=True)
    file_size = models.PositiveBigIntegerField(verbose_name=_("file size"), null=True, blank=True)
    import_mode = models.CharField(
        verbose_name=_("import mode"),
        max_length=30,
        choices=ImportModeChoices,
        default=ImportModeChoices.HISTORY_ONLY,
    )
    total_records = models.PositiveIntegerField(default=0)
    processed_records = models.PositiveIntegerField(default=0)
    created_records = models.PositiveIntegerField(default=0)
    updated_records = models.PositiveIntegerField(default=0)
    skipped_records = models.PositiveIntegerField(default=0)
    duplicate_records = models.PositiveIntegerField(default=0)
    conflict_records = models.PositiveIntegerField(default=0)
    error_records = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    error_details = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ("-started",)
        verbose_name = _("import job")
        verbose_name_plural = _("import jobs")

    def __str__(self):
        return f"{self.source} #{self.pk}" if self.pk else str(self.source)

    def get_absolute_url(self):
        return reverse("plugins:netbox_ip_history:importjob", args=[self.pk])

    def get_status_color(self):
        return ImportStatusChoices.colors.get(self.status)


class HistoricalIPEvent(NetBoxModel):
    """A single point-in-time fact about an IP address, native or imported."""

    timestamp = models.DateTimeField(verbose_name=_("timestamp"))
    snapshot = models.BooleanField(
        verbose_name=_("snapshot"),
        default=False,
        help_text=_("The source gave no change time; the timestamp is when the record was imported."),
    )
    ip_address = models.GenericIPAddressField(verbose_name=_("IP address"))
    prefix_length = models.PositiveSmallIntegerField(null=True, blank=True)
    vrf_name = models.CharField(verbose_name=_("VRF"), max_length=255, blank=True)
    vrf_rd = models.CharField(verbose_name=_("route distinguisher"), max_length=255, blank=True)
    source_scope_identifier = models.CharField(max_length=255, blank=True)
    tenant_name = models.CharField(verbose_name=_("tenant"), max_length=255, blank=True)
    event_type = models.CharField(verbose_name=_("event type"), max_length=30, choices=EventTypeChoices)
    source = models.ForeignKey(
        to=ImportSource, on_delete=models.PROTECT, related_name="events", verbose_name=_("source")
    )
    source_record_id = models.CharField(max_length=255, blank=True)
    source_event_type = models.CharField(max_length=255, blank=True)
    source_username = models.CharField(verbose_name=_("user"), max_length=255, blank=True)
    hostname = models.CharField(verbose_name=_("hostname"), max_length=255, blank=True)
    dns_name = models.CharField(verbose_name=_("DNS name"), max_length=255, blank=True)
    description = models.TextField(verbose_name=_("description"), blank=True)
    owner_type = models.CharField(max_length=64, blank=True)
    owner_name = models.CharField(verbose_name=_("owner"), max_length=255, blank=True)
    interface_name = models.CharField(verbose_name=_("interface"), max_length=255, blank=True)
    mac_address = models.CharField(verbose_name=_("MAC address"), max_length=64, blank=True)
    device_name = models.CharField(verbose_name=_("device"), max_length=255, blank=True)
    virtual_machine_name = models.CharField(verbose_name=_("virtual machine"), max_length=255, blank=True)
    status = models.CharField(verbose_name=_("status"), max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    site = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=255, blank=True)
    tags_snapshot = models.JSONField(default=list, blank=True)
    custom_fields_snapshot = models.JSONField(default=dict, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    fingerprint = models.CharField(max_length=64, unique=True, editable=False)
    import_job = models.ForeignKey(
        to=ImportJob, on_delete=models.CASCADE, related_name="events", null=True, blank=True
    )
    related_netbox_ip = models.ForeignKey(
        to="ipam.IPAddress", on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )

    class Meta:
        ordering = ("-timestamp", "-pk")
        verbose_name = _("historical IP event")
        verbose_name_plural = _("historical IP events")
        indexes = [
            models.Index(fields=("ip_address", "vrf_name", "-timestamp"), name="nih_event_ip_vrf_time"),
            models.Index(fields=("source", "-timestamp"), name="nih_event_source_time"),
            models.Index(fields=("event_type", "-timestamp"), name="nih_event_type_time"),
            models.Index(fields=("import_job",), name="nih_event_job"),
        ]

    def __str__(self):
        return f"{self.ip_address} {self.get_event_type_display()} @ {self.timestamp:%Y-%m-%d %H:%M}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_ip_history:historicalipevent", args=[self.pk])

    def get_event_type_color(self):
        return EventTypeChoices.colors.get(self.event_type)

    @property
    def scope(self):
        return self.vrf_name or self.vrf_rd or GLOBAL_VRF

    @property
    def is_native(self):
        return self.source.source_type == SourceTypeChoices.NETBOX
