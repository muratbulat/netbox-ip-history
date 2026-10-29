from ipam.api.serializers import IPAddressSerializer
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers
from users.api.serializers import UserSerializer

from ..models import HistoricalIPEvent, ImportJob, ImportSource

__all__ = (
    "CompareRowSerializer",
    "HistoricalIPEventSerializer",
    "ImportJobSerializer",
    "ImportSourceSerializer",
    "TimelineEntrySerializer",
)


class ImportSourceSerializer(NetBoxModelSerializer):
    class Meta:
        model = ImportSource
        fields = (
            "id", "url", "display_url", "display", "name", "slug", "source_type", "enabled", "description",
            "source_timezone", "field_mapping", "source_priority", "tags", "custom_fields", "created",
            "last_updated",
        )
        brief_fields = ("id", "url", "display", "name", "slug", "source_type")


class ImportJobSerializer(NetBoxModelSerializer):
    source = ImportSourceSerializer(nested=True, read_only=True)
    user = UserSerializer(nested=True, read_only=True)

    class Meta:
        model = ImportJob
        fields = (
            "id", "url", "display_url", "display", "source", "status", "user", "started", "completed",
            "filename", "file_hash", "file_size", "import_mode", "total_records", "created_records",
            "duplicate_records", "error_records", "summary", "error_details", "tags", "custom_fields",
        )
        read_only_fields = tuple(f for f in fields if f not in ("tags", "custom_fields"))
        brief_fields = ("id", "url", "display", "status", "started")


class HistoricalIPEventSerializer(NetBoxModelSerializer):
    source = ImportSourceSerializer(nested=True, read_only=True)
    import_job = ImportJobSerializer(nested=True, read_only=True)
    related_netbox_ip = IPAddressSerializer(nested=True, read_only=True)

    class Meta:
        model = HistoricalIPEvent
        fields = (
            "id", "url", "display_url", "display", "timestamp", "undated", "ip_address", "prefix_length", "vrf_name",
            "vrf_rd", "source_scope_identifier", "tenant_name", "event_type", "source", "import_job",
            "source_record_id", "source_event_type", "source_username", "hostname", "dns_name", "description",
            "owner_type", "owner_name", "interface_name", "mac_address", "device_name", "virtual_machine_name",
            "status", "location", "site", "role", "raw_data", "fingerprint", "related_netbox_ip", "tags",
            "custom_fields", "created", "last_updated",
        )
        read_only_fields = tuple(f for f in fields if f not in ("tags", "custom_fields"))
        brief_fields = ("id", "url", "display", "timestamp", "ip_address", "event_type")


class TimelineEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    url = serializers.CharField()
    timestamp = serializers.DateTimeField()
    native = serializers.BooleanField()
    source = serializers.CharField()
    event_type = serializers.CharField()
    event_type_display = serializers.CharField()
    ip_address = serializers.CharField()
    vrf = serializers.CharField()
    owner_type = serializers.CharField(allow_blank=True)
    owner_name = serializers.CharField(allow_blank=True)
    interface_name = serializers.CharField(allow_blank=True)
    hostname = serializers.CharField(allow_blank=True)
    dns_name = serializers.CharField(allow_blank=True)
    mac_address = serializers.CharField(allow_blank=True)
    status = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)
    username = serializers.CharField(allow_blank=True)


class CompareRowSerializer(serializers.Serializer):
    source = serializers.CharField()
    native = serializers.BooleanField()
    hostname = serializers.CharField(allow_blank=True)
    owner = serializers.CharField(allow_blank=True)
    dns_name = serializers.CharField(allow_blank=True)
    mac_address = serializers.CharField(allow_blank=True)
    vrf = serializers.CharField()
    status = serializers.CharField(allow_blank=True)
    event_type = serializers.CharField()
    last_seen = serializers.DateTimeField()
