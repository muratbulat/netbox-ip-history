import csv
import re
from typing import Any

from .base import BaseIPAMImporter
from .capabilities import ImportCapability, SupportLevel
from .generic_csv import GenericCSVImporter
from .generic_json import GenericJSONImporter


def parse_gestioip_audit_event(event_str: str) -> dict[str, Any] | None:
    """
    Parse a single GestioIP audit event string.
    Returns parsed dictionary or None if the event is a non-IP system event.
    """
    text = str(event_str or "").strip().strip('"').strip("'")
    if not text:
        return None

    ip_str = None
    prefix_len = None
    hostname = ""
    description = ""
    site = ""
    status = ""
    event_type = "updated"

    # Pattern 1: Colon after IP: "10.0.80.1: ---,---,--- -> dc01,..." or "2001:db8::1: down -> up"
    m_colon = re.match(r"^((?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F:]+?)(?:/(\d{1,3}))?:\s+(.*)$", text)
    if m_colon and (m_colon.group(1).count(".") == 3 or m_colon.group(1).count(":") >= 2):
        ip_str = m_colon.group(1)
        prefix_len = int(m_colon.group(2)) if m_colon.group(2) else None
        rest = m_colon.group(3).strip()

        if " -> " in rest:
            before, after = rest.split(" -> ", 1)
            before_clean = before.strip().lower()
            after_clean = after.strip().lower()
            if before_clean in ("down", "up") and after_clean in ("down", "up"):
                status = after.strip()
                event_type = "status_changed"
                rest = ""
            elif before.strip().startswith("---") or before.strip().startswith("unknown"):
                event_type = "created"
                rest = after
            else:
                event_type = "updated"
                rest = after

        if rest:
            parts = [p.strip().strip("'").strip('"') for p in rest.split(",")]
            if len(parts) >= 1 and parts[0] and parts[0] not in ("---", "unknown"):
                hostname = parts[0]
            if len(parts) >= 2 and parts[1] and parts[1] not in ("---", "unknown"):
                description = parts[1]
            if len(parts) >= 3 and parts[2] and parts[2] not in ("---", "unknown"):
                site = parts[2]

        return {
            "ip_address": ip_str,
            "prefix_length": prefix_len,
            "hostname": hostname,
            "description": description,
            "site": site,
            "status": status,
            "owner_name": hostname or description,
            "event_type": event_type,
        }

    # Pattern 2: IP with slash: "10.0.80.10/dc01,desc,..." or "10.0.80.0/24,vlan80,..."
    m_slash = re.match(r"^([0-9a-fA-F.:]+)/([^,]+)(?:,(.*))?$", text)
    if m_slash and (m_slash.group(1).count(".") == 3 or m_slash.group(1).count(":") >= 2):
        second = m_slash.group(2).strip().strip("'").strip('"')
        if second.isdigit() and int(second) <= 128:
            # Subnet CIDR: "10.0.80.0/24,..." or "2001:db8::/64,..."
            ip_str = m_slash.group(1)
            prefix_len = int(second)
            rest = m_slash.group(3) or ""
            if " -> " in rest:
                event_type = "updated"
                rest = rest.split(" -> ", 1)[1]
            parts = [p.strip().strip("'").strip('"') for p in rest.split(",") if p.strip()]
            if len(parts) >= 1 and parts[0] not in ("---", "unknown"):
                hostname = parts[0]
            if len(parts) >= 2 and parts[1] not in ("---", "unknown"):
                site = parts[1]
            if len(parts) >= 3 and parts[2] not in ("---", "unknown"):
                description = parts[2]
        else:
            # IP/Hostname: "10.0.80.10/dc01"
            ip_str = m_slash.group(1)
            hostname = second
            rest = m_slash.group(3) or ""
            parts = [p.strip().strip("'").strip('"') for p in rest.split(",")]
            if len(parts) >= 1 and parts[0] and parts[0] not in ("---", "unknown"):
                description = parts[0]
            if len(parts) >= 2 and parts[1] and parts[1] not in ("---", "unknown"):
                if not description:
                    description = parts[1]
                else:
                    site = parts[1]
            if len(parts) >= 3 and parts[2] and parts[2] not in ("---", "unknown"):
                site = parts[2]

        return {
            "ip_address": ip_str,
            "prefix_length": prefix_len,
            "hostname": hostname,
            "description": description,
            "site": site,
            "status": status,
            "owner_name": hostname or description,
            "event_type": event_type,
        }

    # Pattern 3: Standalone Subnet or IP: "10.0.80.0/24" or "2001:db8::1"
    m_sub = re.match(r"^([0-9a-fA-F.:]+)(?:/(\d{1,3}))?(?:,(.*))?$", text)
    if m_sub and (m_sub.group(1).count(".") == 3 or m_sub.group(1).count(":") >= 2):
        ip_str = m_sub.group(1)
        prefix_len = int(m_sub.group(2)) if m_sub.group(2) else None
        rest = m_sub.group(3) or ""
        parts = [p.strip().strip("'").strip('"') for p in rest.split(",") if p.strip()]
        if len(parts) >= 1 and parts[0] not in ("---", "unknown"):
            hostname = parts[0]
        if len(parts) >= 2 and parts[1] not in ("---", "unknown"):
            site = parts[1]
        return {
            "ip_address": ip_str,
            "prefix_length": prefix_len,
            "hostname": hostname,
            "description": description,
            "site": site,
            "status": status,
            "owner_name": hostname or description,
            "event_type": event_type,
        }

    # Non-IP system audit log (e.g. "vlan26", "Server Name", "entries older than...")
    return None


class GestioIPImporter(BaseIPAMImporter):
    """Adapter for exported GestioIP inventory lists and audit logs."""
    display_name = "GestioIP"
    support_level = SupportLevel.EXPORT
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.HISTORY_FILE, ImportCapability.ADDRESSES}

    def __init__(self, source, stream, mapping=None, format="csv"):
        super().__init__(source, stream, mapping)
        self.format = format

    def iter_records(self):
        if hasattr(self.stream, "seek"):
            self.stream.seek(0)

        if self.format == "json":
            json_importer = GenericJSONImporter(self.source, self.stream, self.mapping)
            for rec in json_importer.iter_records():
                yield rec
            return

        lines = list(line.decode("utf-8-sig") if isinstance(line, bytes) else line for line in self.stream)
        if not lines:
            return

        reader = csv.DictReader(lines)
        fieldnames = [str(f).strip().lower().replace(" ", "_").replace("-", "_") for f in (reader.fieldnames or []) if f]

        if "event" in fieldnames:
            # Audit log format
            for raw_row in reader:
                if not raw_row or not any(raw_row.values()):
                    continue

                clean_row = {
                    str(k).strip().lower().replace(" ", "_").replace("-", "_"): (v.strip() if isinstance(v, str) else v)
                    for k, v in raw_row.items()
                    if k is not None
                }

                event_str = clean_row.get("event", "")
                parsed = parse_gestioip_audit_event(event_str)
                if not parsed:
                    # Skip non-IP system events
                    continue

                record = {
                    "source_record_id": clean_row.get("id", ""),
                    "source_username": clean_row.get("user", ""),
                    "timestamp": clean_row.get("date", ""),
                    "source_event_type": clean_row.get("event_type", ""),
                    "ip_address": parsed["ip_address"],
                    "prefix_length": parsed["prefix_length"],
                    "hostname": parsed["hostname"],
                    "description": parsed["description"],
                    "site": parsed["site"],
                    "status": parsed["status"],
                    "owner_name": parsed["owner_name"] or parsed["hostname"],
                    "event_type": parsed["event_type"],
                    "raw_data": dict(raw_row),
                }
                yield record
        else:
            # Standard CSV format
            csv_importer = GenericCSVImporter(self.source, lines, self.mapping)
            for rec in csv_importer.iter_records():
                yield rec