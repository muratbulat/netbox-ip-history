"""
Frozen fingerprint algorithms used by data migrations.

The live algorithm is services.normalize.fingerprint(). Every time it changes, its new
version is copied here verbatim and a migration recomputes imported events with it, so
re-importing a file after an upgrade still matches the events it created before. Never edit
an existing function in this module: migrations that already ran depend on it.
"""

import hashlib
from datetime import UTC, datetime

NATIVE_PREFIX = "netbox-oc-"


def _value(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


def fingerprint_v2(source_slug, event):
    fields = (
        "source_record_id", "ip_address", "timestamp", "event_type", "hostname", "dns_name", "owner_name",
        "interface_name", "mac_address", "vrf_name", "vrf_rd", "status", "description",
    )
    values = ("v2", source_slug, *(_value(getattr(event, f)) for f in fields))
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


def recompute(apps, algorithm, batch_size=2000):
    """
    Recompute the fingerprint of every imported (non-native) event with ``algorithm``.

    When several events now share a fingerprint they were duplicates all along: the oldest
    (lowest pk) is kept and the others are deleted. Native ``netbox-oc-<pk>`` events are
    never touched.
    """
    HistoricalIPEvent = apps.get_model("netbox_ip_history", "HistoricalIPEvent")
    imported = (
        HistoricalIPEvent.objects.exclude(source__source_type="netbox")
        .exclude(fingerprint__startswith=NATIVE_PREFIX)
        .select_related("source")
        .order_by("pk")
    )
    keepers, duplicates, changed = set(), [], []
    for event in imported.iterator(chunk_size=batch_size):
        new = algorithm(event.source.slug, event)
        if new in keepers:
            duplicates.append(event.pk)
            continue
        keepers.add(new)
        if event.fingerprint != new:
            event.fingerprint = new
            changed.append(event)

    for start in range(0, len(duplicates), batch_size):
        HistoricalIPEvent.objects.filter(pk__in=duplicates[start:start + batch_size]).delete()
    HistoricalIPEvent.objects.bulk_update(changed, ["fingerprint"], batch_size=batch_size)
    return len(changed), len(duplicates)


def fingerprint_v3(source_slug, event):
    fields = (
        "source_record_id", "ip_address", "timestamp", "event_type", "hostname", "dns_name", "owner_name",
        "interface_name", "mac_address", "vrf_name", "vrf_rd", "status", "description",
    )
    values = (
        "v3",
        source_slug,
        *("" if event.snapshot and f == "timestamp" else _value(getattr(event, f)) for f in fields),
    )
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()
