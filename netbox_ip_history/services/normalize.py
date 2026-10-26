import hashlib
import ipaddress
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from ..choices import EventTypeChoices

__all__ = (
    "RecordError",
    "fingerprint",
    "normalize_event_type",
    "normalize_ip",
    "normalize_timestamp",
    "normalize_vrf",
)

_TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d",
)

_EVENT_ALIASES = {
    "add": "created",
    "added": "created",
    "create": "created",
    "creation": "created",
    "new": "created",
    "remove": "deleted",
    "removed": "deleted",
    "delete": "deleted",
    "deletion": "deleted",
    "change": "updated",
    "changed": "updated",
    "update": "updated",
    "edit": "updated",
    "edited": "updated",
    "modify": "updated",
    "modified": "updated",
    "import": "imported",
    "sync": "imported",
    "manual": "imported",
    "local": "imported",
}


class RecordError(ValueError):
    """A source record that cannot be normalized; reported per row, never fatal to an import."""


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip().strip("'\"").strip()


def normalize_ip(value: Any) -> tuple[str, int | None]:
    """
    Validate and canonicalize an IP address (optionally with /prefix).

    Returns (compressed address, prefix length or None). Integer-encoded addresses (as
    stored by phpIPAM) are accepted. Raises RecordError for anything else, so invalid input
    never reaches a GenericIPAddressField query.
    """
    text = _clean(value)
    if not text:
        raise RecordError("IP address is required")
    try:
        if "/" in text:
            interface = ipaddress.ip_interface(text)
            return interface.ip.compressed, interface.network.prefixlen
        if text.isdigit() and len(text) >= 8:
            return ipaddress.ip_address(int(text)).compressed, None
        return ipaddress.ip_address(text).compressed, None
    except ValueError as exc:
        raise RecordError(f"Invalid IP address: {text}") from exc


def normalize_vrf(value: Any) -> str:
    """Empty string for the global table, however the source spelled it."""
    text = _clean(value)
    return "" if text.lower() in ("global", "default", "none", "-", "---") else text


def _zone(name: str):
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return timezone.get_current_timezone()


def normalize_timestamp(value: Any, source_timezone: str = "", default: datetime | None = None) -> datetime:
    """
    Parse ISO-8601, common day/month orderings or epoch seconds into an aware datetime.

    Naive values are interpreted in ``source_timezone`` and require one. Missing values
    fall back to ``default`` (or now) — used for snapshot exports without change times.
    """
    if isinstance(value, datetime):
        result = value
    else:
        text = _clean(value)
        if not text:
            return default or timezone.now()
        result = None
        try:
            result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            for fmt in _TIMESTAMP_FORMATS:
                try:
                    result = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
        if result is None:
            try:
                result = datetime.fromtimestamp(float(text), tz=_zone(source_timezone))
            except (ValueError, OverflowError, OSError) as exc:
                raise RecordError(f"Invalid timestamp: {text}") from exc

    if timezone.is_naive(result):
        if not source_timezone:
            raise RecordError("Naive timestamp requires a source timezone")
        result = result.replace(tzinfo=_zone(source_timezone))
    return result.astimezone(timezone.get_current_timezone())


def normalize_event_type(value: Any) -> str:
    text = _clean(value).lower().replace(" ", "_")
    if not text:
        return EventTypeChoices.IMPORTED
    mapped = _EVENT_ALIASES.get(text, text)
    return mapped if mapped in EventTypeChoices.values() else EventTypeChoices.IMPORTED


def fingerprint(source: str, record: dict[str, Any]) -> str:
    fields = (
        source,
        record.get("source_record_id", ""),
        record.get("ip_address", ""),
        record.get("timestamp", ""),
        record.get("event_type", ""),
        record.get("hostname", ""),
        record.get("owner_name", ""),
        record.get("interface_name", ""),
        record.get("description", ""),
    )
    return hashlib.sha256("\x1f".join(map(str, fields)).encode("utf-8")).hexdigest()
