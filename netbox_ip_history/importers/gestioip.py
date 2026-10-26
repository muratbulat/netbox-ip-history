"""GestióIP inventory exports and audit logs."""

import re
from typing import Any

from .base import BaseImporter, Capability, SupportLevel, clean_key
from .generic_csv import iter_json_rows

__all__ = ("GestioIPImporter", "parse_gestioip_audit_event")

_EMPTY = ("", "---", "unknown")
_IPV4 = r"(?:\d{1,3}\.){3}\d{1,3}"


def _looks_like_ip(text: str) -> bool:
    return text.count(".") == 3 or text.count(":") >= 2


def _parts(text: str, skip_blank: bool = False) -> list[str]:
    parts = [p.strip().strip("'\"") for p in (text or "").split(",")]
    return [p for p in parts if p] if skip_blank else parts


def _value(parts: list[str], index: int) -> str:
    return parts[index] if len(parts) > index and parts[index] not in _EMPTY else ""


def _result(ip, prefix_len, hostname="", description="", site="", status="", event_type="updated"):
    return {
        "ip_address": ip,
        "prefix_length": prefix_len,
        "hostname": hostname,
        "description": description,
        "site": site,
        "status": status,
        "owner_name": hostname or description,
        "event_type": event_type,
    }


def parse_gestioip_audit_event(event_str: str) -> dict[str, Any] | None:
    """
    Parse the free-text ``event`` column of a GestióIP audit log.

    Returns None for audit entries that don't concern a single IP address
    (VLAN edits, user management, housekeeping, ...).
    """
    text = str(event_str or "").strip().strip("'\"")
    if not text:
        return None

    # "<ip>[/len]: <before> -> <after>" or "<ip>: down -> up"
    match = re.match(rf"^({_IPV4}|[0-9a-fA-F:]+?)(?:/(\d{{1,3}}))?:\s+(.*)$", text)
    if match and _looks_like_ip(match.group(1)):
        prefix_len = int(match.group(2)) if match.group(2) else None
        rest, event_type, status = match.group(3).strip(), "updated", ""
        if " -> " in rest:
            before, after = (s.strip() for s in rest.split(" -> ", 1))
            if before.lower() in ("down", "up") and after.lower() in ("down", "up"):
                return _result(match.group(1), prefix_len, status=after, event_type="status_changed")
            if before.startswith(("---", "unknown")):
                event_type = "created"
            rest = after
        parts = _parts(rest)
        return _result(
            match.group(1), prefix_len, _value(parts, 0), _value(parts, 1), _value(parts, 2), status, event_type
        )

    # "<ip>/<hostname>,<desc>,..." or "<network>/<len>,<name>,<site>,<desc>"
    match = re.match(r"^([0-9a-fA-F.:]+)/([^,]+)(?:,(.*))?$", text)
    if match and _looks_like_ip(match.group(1)):
        second = match.group(2).strip().strip("'\"")
        rest = match.group(3) or ""
        if second.isdigit() and int(second) <= 128:
            event_type = "updated"
            if " -> " in rest:
                rest = rest.split(" -> ", 1)[1]
            parts = _parts(rest, skip_blank=True)
            return _result(
                match.group(1), int(second), _value(parts, 0), _value(parts, 2), _value(parts, 1), event_type=event_type
            )
        parts = _parts(rest)
        description, site = _value(parts, 0), ""
        if _value(parts, 1):
            if description:
                site = _value(parts, 1)
            else:
                description = _value(parts, 1)
        site = _value(parts, 2) or site
        return _result(match.group(1), None, second, description, site)

    # Bare "<ip>[/len][,host,site]"
    match = re.match(r"^([0-9a-fA-F.:]+)(?:/(\d{1,3}))?(?:,(.*))?$", text)
    if match and _looks_like_ip(match.group(1)):
        parts = _parts(match.group(3) or "", skip_blank=True)
        prefix_len = int(match.group(2)) if match.group(2) else None
        return _result(match.group(1), prefix_len, _value(parts, 0), site=_value(parts, 1))

    return None


class GestioIPImporter(BaseImporter):
    """
    GestióIP CSV/JSON exports.

    A CSV with an ``event`` column is treated as an audit log (``id``, ``date``, ``user``,
    ``event_type``, ``event``); anything else is an inventory list using GestióIP's column
    names (``BM`` prefix length, ``network``, ``Name``).
    """

    source_type = "gestioip"
    display_name = "GestióIP"
    support_level = SupportLevel.NATIVE
    capabilities = frozenset({Capability.ADDRESSES, Capability.PREFIXES, Capability.HISTORY})
    aliases = {
        "owner_name": ("name",),
        "hostname": ("hostname",),
        "prefix_length": ("bm",),
        "source_scope_identifier": ("network",),
    }

    def iter_records(self):
        text = self.read_text()
        if self.format == "json":
            for row in iter_json_rows(text):
                yield self.to_record(row)
            return

        rows = list(self.iter_csv_rows(text))
        if not rows or "event" not in {clean_key(k) for k in rows[0] if k}:
            for row in rows:
                yield self.to_record(row)
            return

        for row in rows:
            clean = {clean_key(k): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
            parsed = parse_gestioip_audit_event(clean.get("event", ""))
            if not parsed:
                continue
            yield {
                **parsed,
                "source_record_id": clean.get("id", ""),
                "source_username": clean.get("user", ""),
                "timestamp": clean.get("date", ""),
                "source_event_type": clean.get("event_type", ""),
                "raw_data": dict(row),
            }
