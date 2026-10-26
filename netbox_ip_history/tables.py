import django_tables2 as tables
from django.utils.translation import gettext_lazy as _
from netbox.tables import NetBoxTable, columns

from .models import HistoricalIPEvent, ImportJob, ImportSource

__all__ = ("HistoricalIPEventTable", "ImportJobTable", "ImportSourceTable")


class ImportSourceTable(NetBoxTable):
    name = tables.Column(verbose_name=_("Name"), linkify=True)
    source_type = columns.ChoiceFieldColumn(verbose_name=_("Type"))
    enabled = columns.BooleanColumn(verbose_name=_("Enabled"))
    job_count = columns.LinkedCountColumn(
        viewname="plugins:netbox_ip_history:importjob_list",
        url_params={"source_id": "pk"},
        verbose_name=_("Jobs"),
    )
    event_count = columns.LinkedCountColumn(
        viewname="plugins:netbox_ip_history:historicalipevent_list",
        url_params={"source_id": "pk"},
        verbose_name=_("Events"),
    )
    tags = columns.TagColumn(url_name="plugins:netbox_ip_history:importsource_list")

    class Meta(NetBoxTable.Meta):
        model = ImportSource
        fields = (
            "pk", "id", "name", "slug", "source_type", "enabled", "source_timezone", "source_priority",
            "job_count", "event_count", "description", "tags", "created", "last_updated", "actions",
        )
        default_columns = ("pk", "name", "source_type", "enabled", "job_count", "event_count", "description")


class ImportJobTable(NetBoxTable):
    id = tables.Column(verbose_name=_("ID"), linkify=True)
    source = tables.Column(verbose_name=_("Source"), linkify=True)
    status = columns.ChoiceFieldColumn(verbose_name=_("Status"))
    user = tables.Column(verbose_name=_("User"))
    tags = columns.TagColumn(url_name="plugins:netbox_ip_history:importjob_list")
    actions = columns.ActionsColumn(actions=("delete",))

    class Meta(NetBoxTable.Meta):
        model = ImportJob
        fields = (
            "pk", "id", "source", "status", "started", "completed", "user", "filename", "file_size", "file_hash",
            "import_mode", "total_records", "created_records", "duplicate_records", "error_records", "tags",
            "actions",
        )
        default_columns = (
            "pk", "id", "source", "status", "started", "user", "filename", "total_records", "created_records",
            "duplicate_records", "error_records",
        )


class HistoricalIPEventTable(NetBoxTable):
    timestamp = columns.DateTimeColumn(verbose_name=_("Timestamp"), linkify=True)
    ip_address = tables.Column(verbose_name=_("IP Address"), linkify=True)
    event_type = columns.ChoiceFieldColumn(verbose_name=_("Event"))
    source = tables.Column(verbose_name=_("Source"), linkify=True)
    import_job = tables.Column(verbose_name=_("Import Job"), linkify=True)
    related_netbox_ip = tables.Column(verbose_name=_("NetBox IP"), linkify=True)
    tags = columns.TagColumn(url_name="plugins:netbox_ip_history:historicalipevent_list")
    actions = columns.ActionsColumn(actions=("delete",))

    class Meta(NetBoxTable.Meta):
        model = HistoricalIPEvent
        fields = (
            "pk", "id", "timestamp", "ip_address", "prefix_length", "vrf_name", "vrf_rd", "event_type", "source",
            "import_job", "source_username", "hostname", "dns_name", "owner_type", "owner_name", "device_name",
            "virtual_machine_name", "interface_name", "mac_address", "status", "tenant_name", "site",
            "description", "related_netbox_ip", "tags", "created", "actions",
        )
        default_columns = (
            "pk", "timestamp", "ip_address", "vrf_name", "event_type", "source", "owner_name", "dns_name",
            "interface_name", "source_username",
        )
