import csv
import io
from collections.abc import Iterable, Iterator
from enum import StrEnum
from typing import Any

__all__ = (
    "BaseImporter",
    "Capability",
    "SupportLevel",
    "apply_aliases",
    "clean_key",
    "decode_stream",
)


class Capability(StrEnum):
    ADDRESSES = "addresses"
    PREFIXES = "prefixes"
    VRFS = "vrfs"
    DNS = "dns"
    DEVICES = "devices"
    INTERFACES = "interfaces"
    HISTORY = "history"


class SupportLevel(StrEnum):
    #: Format-specific parser with tests against documented sample data.
    NATIVE = "native"
    #: Generic CSV/JSON/XML parsing with the source's known column aliases.
    GENERIC = "generic"


#: Normalized field name -> accepted source column names (already passed through clean_key()).
DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "ip_address": ("ip_address", "ip", "ipaddress", "ip_addr", "address", "inet", "host_ip", "ipv4", "ipv6"),
    "prefix_length": ("prefix_length", "prefix", "prefixlen", "bm", "bitmask", "mask", "cidr"),
    "timestamp": ("timestamp", "time", "date", "datetime", "last_updated", "modified", "created"),
    "event_type": ("event_type", "event", "action", "operation", "update_type", "type"),
    "hostname": ("hostname", "host", "host_name", "fqdn", "dns_name", "dns"),
    "dns_name": ("dns_name", "dns", "fqdn", "hostname"),
    "owner_name": ("owner_name", "owner", "name", "device_name", "server", "vm_name", "assigned_host"),
    "description": ("description", "desc", "comment", "comments", "note", "notes"),
    "vrf_name": ("vrf_name", "vrf", "scope", "network_view", "partition"),
    "vrf_rd": ("vrf_rd", "rd", "route_distinguisher"),
    "tenant_name": ("tenant_name", "tenant", "customer"),
    "site": ("site", "location", "datacenter"),
    "status": ("status", "state"),
    "mac_address": ("mac_address", "mac", "mac_addr", "hw_addr"),
    "interface_name": ("interface_name", "interface", "port", "nic"),
    "source_username": ("source_username", "username", "user", "user_name", "author", "modified_by"),
    "source_record_id": ("source_record_id", "record_id", "id"),
    "source_scope_identifier": ("source_scope_identifier", "network", "subnet"),
}


def clean_key(key: Any) -> str:
    return str(key).strip().lower().replace(" ", "_").replace("-", "_")


def apply_aliases(row: dict[str, Any], mapping: dict[str, str], aliases: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    """
    Map a raw source row onto normalized field names.

    Explicit ``mapping`` (normalized field -> source column) wins over aliases.
    Empty source values are never treated as evidence.
    """
    clean = {clean_key(k): v.strip() if isinstance(v, str) else v for k, v in row.items() if k is not None}
    record: dict[str, Any] = {}
    for target, column in mapping.items():
        value = clean.get(clean_key(column))
        if value not in (None, ""):
            record[target] = value
    for target, names in aliases.items():
        if record.get(target) not in (None, ""):
            continue
        for name in names:
            value = clean.get(name)
            if value not in (None, ""):
                record[target] = value
                break
    return record


def decode_stream(stream) -> str:
    if hasattr(stream, "seek"):
        stream.seek(0)
    data = stream.read()
    if isinstance(data, bytes):
        data = data.decode("utf-8-sig")
    return data.lstrip("﻿")


class BaseImporter:
    """
    Contract for all importers.

    ``iter_records()`` yields dicts of normalized field names (see DEFAULT_ALIASES) plus a
    ``raw_data`` dict preserving the source-native row. Normalization (IP/timestamp
    canonicalization, fingerprinting) happens centrally in services.import_service.
    """

    source_type: str = ""
    display_name: str = ""
    support_level: SupportLevel = SupportLevel.GENERIC
    capabilities: frozenset[Capability] = frozenset({Capability.ADDRESSES, Capability.HISTORY})
    formats: tuple[str, ...] = ("csv", "json")
    #: Extra source-specific aliases, merged in front of DEFAULT_ALIASES.
    aliases: dict[str, tuple[str, ...]] = {}

    def __init__(self, source, stream, *, format: str = "csv", delimiter: str = ",", mapping: dict | None = None):
        self.source = source
        self.stream = stream
        self.format = format
        self.delimiter = delimiter or ","
        self.mapping = dict(mapping if mapping is not None else (getattr(source, "field_mapping", None) or {}))

    @classmethod
    def get_aliases(cls) -> dict[str, tuple[str, ...]]:
        merged = dict(DEFAULT_ALIASES)
        for target, names in cls.aliases.items():
            merged[target] = tuple(names) + tuple(n for n in merged.get(target, ()) if n not in names)
        return merged

    def iter_records(self) -> Iterator[dict[str, Any]]:
        raise NotImplementedError

    def read_text(self) -> str:
        return decode_stream(self.stream)

    def iter_csv_rows(self, text: str | None = None) -> Iterable[dict[str, Any]]:
        text = self.read_text() if text is None else text
        reader = csv.DictReader(io.StringIO(text), delimiter=self.delimiter)
        for row in reader:
            if row and any((v or "").strip() for v in row.values() if isinstance(v, str)):
                yield row

    def to_record(self, row: dict[str, Any]) -> dict[str, Any]:
        record = apply_aliases(row, self.mapping, self.get_aliases())
        record["raw_data"] = {str(k): v for k, v in row.items() if k is not None}
        return record
