try:
    from rest_framework import serializers
except ImportError:
    class _MockSerializer:
        class ModelSerializer:
            def __init__(self, *args, **kwargs):
                pass
    serializers = _MockSerializer()

from ..models import HistoricalIPEvent, ImportJob, ImportSource


class ImportSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportSource
        fields = (
            "id",
            "name",
            "slug",
            "source_type",
            "enabled",
            "description",
            "source_timezone",
            "field_mapping",
            "support_level",
            "capabilities",
            "source_priority",
            "created",
            "last_updated",
        )


class ImportJobSerializer(serializers.ModelSerializer):
    source = ImportSourceSerializer(read_only=True)

    class Meta:
        model = ImportJob
        fields = (
            "id",
            "source",
            "started",
            "completed",
            "status",
            "filename",
            "file_size",
            "import_mode",
            "total_records",
            "processed_records",
            "created_records",
            "updated_records",
            "skipped_records",
            "duplicate_records",
            "conflict_records",
            "error_records",
            "dry_run",
            "summary",
        )


class HistoricalIPEventSerializer(serializers.ModelSerializer):
    source = ImportSourceSerializer(read_only=True)

    class Meta:
        model = HistoricalIPEvent
        fields = (
            "id",
            "timestamp",
            "ip_address",
            "prefix_length",
            "vrf_name",
            "vrf_rd",
            "source_scope_identifier",
            "tenant_name",
            "event_type",
            "source",
            "source_record_id",
            "source_event_type",
            "source_username",
            "hostname",
            "dns_name",
            "description",
            "owner_type",
            "owner_name",
            "interface_name",
            "mac_address",
            "device_name",
            "virtual_machine_name",
            "status",
            "location",
            "site",
            "role",
            "tags_snapshot",
            "custom_fields_snapshot",
            "raw_data",
            "fingerprint",
            "import_job",
            "related_netbox_ip",
        )
