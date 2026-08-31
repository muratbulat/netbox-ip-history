import hashlib
import ipaddress
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

try:
    from django.utils import timezone
except ImportError:
    from datetime import timezone as _timezone

    class _TimezoneFallback:
        @staticmethod
        def is_naive(value):
            return value.tzinfo is None or value.utcoffset() is None

        @staticmethod
        def get_current_timezone():
            return _timezone.utc

        @staticmethod
        def now():
            return datetime.now(_timezone.utc)

    timezone = _TimezoneFallback()

try:
    from ..choices import EventType
except ImportError:
    class EventType:
        values = {
            "created", "deleted", "updated", "assigned", "unassigned",
            "reassigned", "hostname_changed", "dns_changed", "status_changed",
            "description_changed", "owner_changed", "interface_changed",
            "imported", "discovered", "unknown"
        }
        UNKNOWN = "unknown"
        IMPORTED = "imported"


class RecordError(ValueError):
    pass


def normalize_ip(value: Any) -> tuple[str, int | None]:
    text = str(value or "").strip().strip('"').strip("'")
    if not text:
        raise RecordError("IP address is required")
    if "/" in text:
        try:
            interface = ipaddress.ip_interface(text)
            return interface.ip.compressed, interface.network.prefixlen
        except ValueError as exc:
            raise RecordError(f"Invalid IP address: {text}") from exc
    else:
        try:
            return ipaddress.ip_address(text).compressed, None
        except ValueError as exc:
            raise RecordError(f"Invalid IP address: {text}") from exc


def get_safe_zoneinfo(tz_name: str):
    if not tz_name:
        return timezone.get_current_timezone()
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.get_current_timezone()


def normalize_timestamp(value: Any, source_timezone: str = "") -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        text = str(value or "").strip().strip('"').strip("'")
        if not text:
            result = timezone.now() if hasattr(timezone, "now") else datetime.now(get_safe_zoneinfo(source_timezone))
        else:
            parsed = False
            # Try ISO format
            try:
                result = datetime.fromisoformat(text.replace("Z", "+00:00"))
                parsed = True
            except ValueError:
                pass

            if not parsed:
                # Common date formats in CSV exports
                formats = (
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
                for fmt in formats:
                    try:
                        result = datetime.strptime(text, fmt)
                        parsed = True
                        break
                    except ValueError:
                        continue

            if not parsed:
                try:
                    epoch = float(text)
                    result = datetime.fromtimestamp(epoch, tz=get_safe_zoneinfo(source_timezone))
                    parsed = True
                except (ValueError, OSError):
                    pass

            if not parsed:
                raise RecordError(f"Invalid timestamp: {text}")

    if timezone.is_naive(result):
        if not source_timezone:
            raise RecordError("Naive timestamp requires a source timezone")
        result = result.replace(tzinfo=get_safe_zoneinfo(source_timezone))
    return result.astimezone(timezone.get_current_timezone())


def normalize_event_type(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "_").strip('"').strip("'")
    if not text:
        return getattr(EventType, "IMPORTED", "imported")
    aliases = {
        "add": "created",
        "added": "created",
        "create": "created",
        "creation": "created",
        "remove": "deleted",
        "removed": "deleted",
        "delete": "deleted",
        "deletion": "deleted",
        "change": "updated",
        "changed": "updated",
        "update": "updated",
        "updated": "updated",
        "edit": "updated",
        "edited": "updated",
        "dns": "updated",
        "local": "imported",
        "manual": "imported",
        "sync": "imported",
        "import": "imported",
        "imported": "imported",
    }
    mapped = aliases.get(text, text)
    return mapped if mapped in EventType.values else getattr(EventType, "IMPORTED", "imported")


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