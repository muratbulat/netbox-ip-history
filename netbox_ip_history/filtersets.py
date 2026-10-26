import contextlib

import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from netbox.filtersets import NetBoxModelFilterSet
from utilities.filtersets import register_filterset

from .choices import EventTypeChoices, ImportStatusChoices, SourceTypeChoices
from .models import HistoricalIPEvent, ImportJob, ImportSource
from .services.normalize import RecordError, normalize_ip

__all__ = ("HistoricalIPEventFilterSet", "ImportJobFilterSet", "ImportSourceFilterSet")


@register_filterset
class ImportSourceFilterSet(NetBoxModelFilterSet):
    source_type = django_filters.MultipleChoiceFilter(choices=SourceTypeChoices)

    class Meta:
        model = ImportSource
        fields = ("id", "name", "slug", "source_type", "enabled", "source_timezone", "source_priority")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(slug__icontains=value) | Q(description__icontains=value)
        )


@register_filterset
class ImportJobFilterSet(NetBoxModelFilterSet):
    source_id = django_filters.ModelMultipleChoiceFilter(queryset=ImportSource.objects.all(), label=_("Source (ID)"))
    source = django_filters.ModelMultipleChoiceFilter(
        field_name="source__slug", queryset=ImportSource.objects.all(), to_field_name="slug", label=_("Source (slug)")
    )
    status = django_filters.MultipleChoiceFilter(choices=ImportStatusChoices)

    class Meta:
        model = ImportJob
        fields = ("id", "status", "import_mode", "filename", "file_hash", "started", "completed")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(filename__icontains=value) | Q(file_hash__istartswith=value) | Q(source__name__icontains=value)
        )


@register_filterset
class HistoricalIPEventFilterSet(NetBoxModelFilterSet):
    ip_address = django_filters.CharFilter(method="filter_ip_address", label=_("IP address"))
    source_id = django_filters.ModelMultipleChoiceFilter(queryset=ImportSource.objects.all(), label=_("Source (ID)"))
    source = django_filters.ModelMultipleChoiceFilter(
        field_name="source__slug", queryset=ImportSource.objects.all(), to_field_name="slug", label=_("Source (slug)")
    )
    import_job_id = django_filters.ModelMultipleChoiceFilter(
        queryset=ImportJob.objects.all(), label=_("Import job (ID)")
    )
    event_type = django_filters.MultipleChoiceFilter(choices=EventTypeChoices)
    vrf = django_filters.CharFilter(method="filter_vrf", label=_("VRF (name, RD or 'Global')"))
    timestamp_after = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="gte")
    timestamp_before = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="lte")

    class Meta:
        model = HistoricalIPEvent
        fields = (
            "id",
            "timestamp",
            "prefix_length",
            "vrf_name",
            "vrf_rd",
            "tenant_name",
            "hostname",
            "dns_name",
            "owner_name",
            "owner_type",
            "interface_name",
            "mac_address",
            "device_name",
            "virtual_machine_name",
            "status",
            "source_username",
            "source_record_id",
        )

    def search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        query = (
            Q(hostname__icontains=value)
            | Q(dns_name__icontains=value)
            | Q(owner_name__icontains=value)
            | Q(mac_address__icontains=value)
            | Q(description__icontains=value)
            | Q(source_username__icontains=value)
        )
        with contextlib.suppress(RecordError):
            query |= Q(ip_address=normalize_ip(value)[0])
        return queryset.filter(query)

    def filter_ip_address(self, queryset, name, value):
        try:
            return queryset.filter(ip_address=normalize_ip(value)[0])
        except RecordError:
            return queryset.none()

    def filter_vrf(self, queryset, name, value):
        value = value.strip()
        if value.lower() == "global":
            return queryset.filter((Q(vrf_name="") | Q(vrf_name__iexact="global")) & Q(vrf_rd=""))
        return queryset.filter(Q(vrf_name__icontains=value) | Q(vrf_rd__icontains=value))
