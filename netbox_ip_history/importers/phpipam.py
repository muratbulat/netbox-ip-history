"""phpIPAM address and changelog exports (CSV or JSON, including API ``data`` envelopes)."""

from .base import BaseImporter, Capability, SupportLevel
from .generic_csv import iter_json_rows

__all__ = ("PhpIPAMImporter",)


class PhpIPAMImporter(BaseImporter):
    source_type = "phpipam"
    display_name = "phpIPAM"
    support_level = SupportLevel.NATIVE
    capabilities = frozenset({Capability.ADDRESSES, Capability.PREFIXES, Capability.DNS, Capability.HISTORY})
    # phpIPAM column/field names (addresses table and changelog).
    aliases = {
        "ip_address": ("ip", "ip_addr"),
        "prefix_length": ("subnet", "mask"),
        "hostname": ("hostname",),
        "dns_name": ("dns", "hostname"),
        "owner_name": ("owner",),
        "description": ("note", "description"),
        "mac_address": ("mac",),
        "interface_name": ("port",),
        "event_type": ("action", "caction"),
        "timestamp": ("date", "cdate", "editdate"),
        "source_username": ("username", "cuser"),
        "source_record_id": ("cid", "id"),
    }

    def __init__(self, source, stream, *, format="json", **kwargs):
        super().__init__(source, stream, format=format, **kwargs)

    def iter_records(self):
        text = self.read_text()
        rows = iter_json_rows(text) if self.format == "json" else self.iter_csv_rows(text)
        for row in rows:
            record = self.to_record(row)
            # phpIPAM stores device ownership as a device name only when joined in the export.
            if not record.get("device_name") and row.get("device"):
                record["device_name"] = row["device"]
            yield record
