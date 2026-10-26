"""
Changelog exports from another NetBox instance.

Accepts the JSON returned by ``/api/core/object-changes/`` (a paginated ``results``
envelope, a plain list, or JSON Lines). Only ``ipam.ipaddress`` changes are imported.
Payloads are interpreted from their own content: object IDs from the remote instance are
never resolved against this one.
"""

from ..services.timeline import ObjectLookup, describe_change
from .base import BaseImporter, Capability, SupportLevel
from .generic_csv import iter_json_rows

__all__ = ("NetBoxExportImporter",)


def _is_ipaddress_change(row: dict) -> bool:
    object_type = row.get("changed_object_type")
    if isinstance(object_type, dict):
        object_type = f"{object_type.get('app_label', '')}.{object_type.get('model', '')}"
    return str(object_type or "").lower() == "ipam.ipaddress"


class NetBoxExportImporter(BaseImporter):
    source_type = "netbox_export"
    display_name = "NetBox changelog export"
    support_level = SupportLevel.NATIVE
    capabilities = frozenset(
        {Capability.ADDRESSES, Capability.VRFS, Capability.DNS, Capability.INTERFACES, Capability.HISTORY}
    )
    formats = ("json",)

    def iter_records(self):
        lookup = ObjectLookup(resolve=False)
        for row in iter_json_rows(self.read_text()):
            if not _is_ipaddress_change(row):
                continue
            fields = describe_change(row, lookup)
            if fields is None:
                continue
            yield {
                **fields,
                "timestamp": row.get("time"),
                "source_record_id": str(row.get("id") or ""),
                "raw_data": row,
            }
