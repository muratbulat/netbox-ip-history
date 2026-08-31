try:
    import django_filters
    from netbox.filtersets import BaseFilterSet
    FilterSetClass = BaseFilterSet
except ImportError:
    try:
        import django_filters
        FilterSetClass = django_filters.FilterSet
    except ImportError:
        django_filters = None
        FilterSetClass = None


if FilterSetClass:
    from .choices import EventType, JobStatus, SourceType
    from .models import HistoricalIPEvent, ImportJob, ImportSource

    class ImportSourceFilterSet(FilterSetClass):
        source_type = django_filters.MultipleChoiceFilter(choices=SourceType.choices)

        class Meta:
            model = ImportSource
            fields = ("id", "name", "slug", "source_type", "enabled")

    class ImportJobFilterSet(FilterSetClass):
        status = django_filters.MultipleChoiceFilter(choices=JobStatus.choices)

        class Meta:
            model = ImportJob
            fields = ("id", "source", "status", "dry_run", "import_mode")

    class HistoricalIPEventFilterSet(FilterSetClass):
        event_type = django_filters.MultipleChoiceFilter(choices=EventType.choices)

        class Meta:
            model = HistoricalIPEvent
            fields = (
                "id",
                "ip_address",
                "event_type",
                "source",
                "vrf_name",
                "hostname",
                "dns_name",
                "owner_name",
                "mac_address",
            )
else:
    class ImportSourceFilterSet:
        pass

    class ImportJobFilterSet:
        pass

    class HistoricalIPEventFilterSet:
        pass
