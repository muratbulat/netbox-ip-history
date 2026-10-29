"""
Infoblox NIOS CSV exports.

NIOS CSV files are sectioned: a row whose first cell is ``header-<object>`` defines the
columns for the following rows whose first cell is ``<object>`` (for example
``header-hostrecord`` / ``hostrecord``). Required columns carry a ``*`` suffix
(``fqdn*``, ``address*``). Supported objects: host, A, AAAA and PTR records and IPv4/IPv6
fixed addresses. A host record row may list several addresses; one record is emitted per
address. Exports carry no change timestamps, so each row is an inventory snapshot taken at
import time.
"""

import csv
import io

from ..services.normalize import RecordError, normalize_ip
from .base import BaseImporter, Capability, SupportLevel, clean_key

__all__ = ("InfobloxImporter",)

_ADDRESS_COLUMNS = ("address", "addresses", "ipv4addr", "ip_address", "ipv6_addresses", "ipv6addr")
_NAME_COLUMNS = ("fqdn", "name", "dname", "host_name")
_SUPPORTED_OBJECTS = {
    "hostrecord",
    "arecord",
    "aaaarecord",
    "ptrrecord",
    "fixedaddress",
    "ipv6fixedaddress",
}


def _column(name: str) -> str:
    return clean_key(name.rstrip("*"))


class InfobloxImporter(BaseImporter):
    source_type = "infoblox"
    display_name = "Infoblox NIOS"
    support_level = SupportLevel.NATIVE
    capabilities = frozenset({Capability.ADDRESSES, Capability.DNS, Capability.VRFS})
    formats = ("csv",)

    def iter_records(self):
        headers: dict[str, list[str]] = {}
        reader = csv.reader(io.StringIO(self.read_text()))
        for cells in reader:
            if not cells or not cells[0].strip():
                continue
            kind = cells[0].strip().lower()
            if kind.startswith("header-"):
                headers[kind.removeprefix("header-")] = [_column(c) for c in cells[1:]]
                continue
            if kind not in _SUPPORTED_OBJECTS or kind not in headers:
                continue
            row = dict(zip(headers[kind], (c.strip() for c in cells[1:]), strict=False))
            yield from self._records_for(kind, row)

    def _records_for(self, kind: str, row: dict[str, str]):
        addresses = []
        for column in _ADDRESS_COLUMNS:
            addresses.extend(a.strip() for a in (row.get(column) or "").split(",") if a.strip())
        name = next((row[c] for c in _NAME_COLUMNS if row.get(c)), "")
        for address in addresses:
            try:
                canonical = normalize_ip(address)[0]
            except RecordError:
                canonical = address
            record = {
                "ip_address": address,
                "event_type": "imported",
                "source_event_type": kind,
                "hostname": name,
                "dns_name": name,
                "mac_address": row.get("mac_address", ""),
                "description": row.get("comment", ""),
                "vrf_name": row.get("network_view", ""),
                "source_scope_identifier": row.get("view", ""),
                # Stable across exports: never derived from the row's position in the file.
                "source_record_id": f"{kind}:{canonical}:{name}",
                "raw_data": {"object": kind, **row},
            }
            yield {k: v for k, v in record.items() if v not in (None, "")}
