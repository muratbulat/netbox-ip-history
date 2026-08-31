import csv

from .base import BaseIPAMImporter
from .capabilities import ImportCapability, SupportLevel

DEFAULT_FIELD_ALIASES = {
    "ip_address": (
        "ip_address", "ip", "ipaddress", "ip_addr", "ip addr", "ip address",
        "inet", "address", "host_ip", "host ip", "ip_v4", "ipv4", "ip_v6", "ipv6"
    ),
    "owner_name": (
        "name", "owner_name", "server_name", "server", "vm_name", "device_name",
        "assigned_host", "host_name_short", "short_name", "owner"
    ),
    "hostname": (
        "hostname", "host", "host_name", "fqdn", "dns_name", "dns", "host2", "host_2"
    ),
    "dns_name": (
        "dns_name", "dns", "fqdn", "hostname"
    ),
    "description": (
        "description", "desc", "comment", "comments", "comentario", "notes",
        "note", "aciklama", "açıklama"
    ),
    "prefix_length": (
        "prefix_length", "prefix", "prefixlen", "bm", "bitmask", "mask",
        "subnet_mask", "netmask", "cidr"
    ),
    "vrf_name": (
        "vrf_name", "vrf", "vrf_rd", "route_distinguisher", "scope", "partition"
    ),
    "tenant_name": (
        "tenant_name", "tenant", "customer", "client", "owner"
    ),
    "site": (
        "site", "location", "datacenter", "dc", "building"
    ),
    "status": (
        "status", "state", "acik/kapali", "açık/kapalı", "acik_kapali", "ping", "active"
    ),
    "mac_address": (
        "mac_address", "mac", "mac_addr", "hw_addr", "ethernet"
    ),
    "interface_name": (
        "interface_name", "interface", "intf", "port", "nic"
    ),
    "timestamp": (
        "timestamp", "time", "date", "fecha", "last_updated", "created", "modified", "datetime"
    ),
    "event_type": (
        "event_type", "event", "action", "type", "update_type", "update type", "operation"
    ),
    "source_username": (
        "source_username", "username", "user", "author", "modified_by", "usuario"
    ),
    "source_scope_identifier": (
        "source_scope_identifier", "network", "subnet", "subnet_address"
    ),
}


class GenericCSVImporter(BaseIPAMImporter):
    display_name = "Generic CSV / TSV"
    support_level = SupportLevel.EXPORT
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.HISTORY_FILE, ImportCapability.ADDRESSES}

    def __init__(self, source, stream, mapping=None, delimiter=","):
        super().__init__(source, stream, mapping)
        self.delimiter = delimiter

    def iter_records(self):
        if hasattr(self.stream, "seek"):
            self.stream.seek(0)
        lines = (line.decode("utf-8-sig") if isinstance(line, bytes) else line for line in self.stream)
        reader = csv.DictReader(lines, delimiter=self.delimiter)

        mapping = self.mapping or getattr(self.source, "field_mapping", {}) or {}

        for raw_row in reader:
            if not raw_row or not any(raw_row.values()):
                continue

            clean_row = {}
            for k, v in raw_row.items():
                if k is None:
                    continue
                clean_k = str(k).strip().lower().replace(" ", "_").replace("-", "_")
                val = v.strip() if isinstance(v, str) else v
                clean_row[clean_k] = val

            record = {}
            # 1. Apply explicit mapping if provided
            for target, column in mapping.items():
                norm_col = str(column).strip().lower().replace(" ", "_").replace("-", "_")
                if norm_col in clean_row and clean_row[norm_col] != "":
                    record[target] = clean_row[norm_col]

            # 2. Fill missing targets using DEFAULT_FIELD_ALIASES
            for target, aliases in DEFAULT_FIELD_ALIASES.items():
                if target not in record or not record[target]:
                    for alias in aliases:
                        norm_alias = alias.replace(" ", "_").replace("-", "_")
                        if norm_alias in clean_row and clean_row[norm_alias] != "":
                            record[target] = clean_row[norm_alias]
                            break

            record["raw_data"] = dict(raw_row)
            yield record