import hashlib
import ipaddress
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from ..choices import EventTypeChoices

__all__ = (
    "FINGERPRINT_VERSION",
    "RecordError",
    "fingerprint",
    "normalize_event_type",
    "normalize_ip",
    "normalize_prefix_length",
    "normalize_timestamp",
    "normalize_vrf",
)

_DAY_FIRST = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")
_MONTH_FIRST = ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y")
_UNAMBIGUOUS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d",
)
#: Formats tried in order. Slash dates follow the source's preferred order first; the other order
#: only applies when the preferred one cannot parse the value (e.g. 13/04/2025 is day-first).
_TIMESTAMP_FORMATS = {
    "dmy": (*_UNAMBIGUOUS[:3], *_DAY_FIRST, *_MONTH_FIRST, *_UNAMBIGUOUS[3:]),
    "mdy": (*_UNAMBIGUOUS[:3], *_MONTH_FIRST, *_DAY_FIRST, *_UNAMBIGUOUS[3:]),
}

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


def normalize_prefix_length(value: Any, ip: str) -> int | None:
    """
    Prefix length for ``ip`` from a length ("24") or an IPv4 dotted netmask ("255.255.255.0").

    Returns None for anything not valid for the address family (e.g. 64 for an IPv4 address,
    or a non-contiguous mask), so callers can fall back to another source of the prefix.
    """
    text = _clean(value)
    if not text:
        return None
    version = ipaddress.ip_address(ip).version
    if text.isdigit():
        length = int(text)
        return length if length <= (32 if version == 4 else 128) else None
    if version == 4 and text.count(".") == 3:
        try:
            return ipaddress.IPv4Network(f"0.0.0.0/{text}").prefixlen
        except ValueError:
            return None
    return None


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


def normalize_timestamp(
    value: Any, source_timezone: str = "", default: datetime | None = None, date_order: str = "dmy"
) -> datetime:
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
            for fmt in _TIMESTAMP_FORMATS.get(date_order, _TIMESTAMP_FORMATS["dmy"]):
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


#: Bump whenever the fingerprint inputs change, and add a data migration that recomputes the
#: fingerprints of imported events with a frozen copy of the new algorithm.
FINGERPRINT_VERSION = 3

#: Event fields identifying an imported record, in hashing order.
FINGERPRINT_FIELDS = (
    "source_record_id",
    "ip_address",
    "timestamp",
    "event_type",
    "hostname",
    "dns_name",
    "owner_name",
    "interface_name",
    "mac_address",
    "vrf_name",
    "vrf_rd",
    "status",
    "description",
)


def _fingerprint_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


def fingerprint(source: str, record: dict[str, Any]) -> str:
    """
    Stable identity of an imported record; equal fingerprints within a source are duplicates.

    Undated records (no change time in the source) are identified without their timestamp,
    which is only the import time, so re-importing the same snapshot matches what it created.
    """
    undated = bool(record.get("undated"))
    values = (
        f"v{FINGERPRINT_VERSION}",
        source,
        *("" if undated and f == "timestamp" else _fingerprint_value(record.get(f)) for f in FINGERPRINT_FIELDS),
    )
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()
