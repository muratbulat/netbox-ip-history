try:
    import django_tables2 as tables
    from netbox.tables import NetBoxTable, columns
    TableClass = NetBoxTable
except ImportError:
    try:
        import django_tables2 as tables
        TableClass = tables.Table
        columns = None
    except ImportError:
        tables = None
        TableClass = None
        columns = None

if TableClass:
    from .models import HistoricalIPEvent, ImportJob, ImportSource

    class ImportSourceTable(TableClass):
        name = tables.Column(linkify=True)

        class Meta(getattr(TableClass, "Meta", object)):
            model = ImportSource
            fields = ("pk", "id", "name", "slug", "source_type", "enabled", "description", "created", "last_updated")
            default_columns = ("name", "source_type", "enabled", "description", "last_updated")

    class ImportJobTable(TableClass):
        id = tables.Column(linkify=True)
        source = tables.Column(linkify=True)

        class Meta(getattr(TableClass, "Meta", object)):
            model = ImportJob
            fields = (
                "pk",
                "id",
                "source",
                "started",
                "completed",
                "status",
                "filename",
                "total_records",
                "processed_records",
                "created_records",
                "updated_records",
                "dry_run",
            )
            default_columns = ("id", "source", "started", "status", "filename", "total_records", "processed_records", "dry_run")

    class HistoricalIPEventTable(TableClass):
        timestamp = tables.DateTimeColumn()
        ip_address = tables.Column()
        event_type = tables.Column()
        source = tables.Column()

        class Meta(getattr(TableClass, "Meta", object)):
            model = HistoricalIPEvent
            fields = (
                "pk",
                "id",
                "timestamp",
                "ip_address",
                "event_type",
                "source",
                "vrf_name",
                "hostname",
                "owner_name",
                "mac_address",
                "status",
            )
            default_columns = ("timestamp", "ip_address", "event_type", "source", "vrf_name", "hostname", "owner_name")

    HISTORY_COLUMN_TEMPLATE = """
    {% if record.address.ip %}
    <a href="{% url 'plugins:netbox_ip_history:history' %}?ip={{ record.address.ip }}"
       class="btn btn-sm btn-outline-primary py-0 px-1" title="View IP History">
        <span class="mdi mdi-history"></span>
    </a>
    {% endif %}
    """

    if columns:
        try:
            from utilities.tables import register_table_column
            from ipam.tables import IPAddressTable, AnnotatedIPAddressTable

            register_table_column(
                IPAddressTable,
                "ip_history",
                columns.TemplateColumn(
                    template_code=HISTORY_COLUMN_TEMPLATE,
                    verbose_name="History",
                ),
            )
            register_table_column(
                AnnotatedIPAddressTable,
                "ip_history",
                columns.TemplateColumn(
                    template_code=HISTORY_COLUMN_TEMPLATE,
                    verbose_name="History",
                ),
            )
        except Exception:
            # Best-effort integration into NetBox's own IP Address tables —
            # a failure here (e.g. a NetBox version that changed
            # register_table_column's signature) should not break the
            # plugin's own pages, but silently vanishing left admins no way
            # to know the "History" column is missing. Not a hard failure:
            # module import time is too early for request-scoped logging
            # config, so this only reaches a handler if one is already
            # attached (e.g. NetBox's default logging.yaml).
            import logging
            logging.getLogger("netbox.plugins.netbox_ip_history").warning(
                "Failed to register ip_history column on native IPAddressTable/AnnotatedIPAddressTable",
                exc_info=True,
            )
else:
    class ImportSourceTable:
        pass

    class ImportJobTable:
        pass

    class HistoricalIPEventTable:
        pass
