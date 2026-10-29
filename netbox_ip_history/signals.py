"""Real-time capture of native NetBox IP address changes."""

import logging

from core.models import ObjectChange
from django.db import DEFAULT_DB_ALIAS, transaction
from django.db.models import BigIntegerField
from django.db.models.functions import Cast
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from netbox.plugins import get_plugin_config

logger = logging.getLogger("netbox.plugins.netbox_ip_history")

__all__ = ("backfill_native_events", "get_native_source", "record_object_changes")

_UPSERT_FIELDS = (
    "timestamp",
    "ip_address",
    "prefix_length",
    "vrf_name",
    "tenant_name",
    "event_type",
    "source_event_type",
    "source_username",
    "hostname",
    "dns_name",
    "description",
    "owner_name",
    "owner_type",
    "interface_name",
    "status",
    "raw_data",
    "related_netbox_ip",
)


def get_native_source():
    """The singleton ImportSource representing NetBox itself (re-created if deleted)."""
    from django.core.exceptions import ImproperlyConfigured

    from .choices import SourceTypeChoices
    from .models import NATIVE_SOURCE_SLUG, ImportSource

    if ImportSource.objects.filter(slug=NATIVE_SOURCE_SLUG).exclude(source_type=SourceTypeChoices.NETBOX).exists():
        raise ImproperlyConfigured(
            f"ImportSource {NATIVE_SOURCE_SLUG!r} is not of type 'netbox'; rename it so native history can be recorded."
        )
    source, _ = ImportSource.objects.get_or_create(
        slug=NATIVE_SOURCE_SLUG,
        source_type=SourceTypeChoices.NETBOX,
        defaults={
            "name": "NetBox",
            "description": "Native NetBox IP address lifecycle events",
            "source_priority": 1,
        },
    )
    return source


def record_object_changes(changes, source=None, lookup=None) -> list:
    """
    Upsert HistoricalIPEvents for ipaddress ObjectChanges (idempotent per ObjectChange).

    Writes go through a single bulk upsert: no per-object save() signals, so recording an
    audit event never produces a change-log entry of its own.
    """
    from ipam.models import IPAddress

    from .models import HistoricalIPEvent
    from .services.timeline import ObjectLookup, describe_change

    changes = [c for c in changes if c.changed_object_type.model == "ipaddress"]
    if not changes:
        return []
    source = source or get_native_source()
    lookup = lookup or ObjectLookup(p for c in changes for p in (c.prechange_data, c.postchange_data))
    live_ips = set(
        IPAddress.objects.filter(pk__in={c.changed_object_id for c in changes}).values_list("pk", flat=True)
    )

    events = []
    for change in changes:
        fields = describe_change(change, lookup)
        if fields is None:
            continue
        events.append(
            HistoricalIPEvent(
                **fields,
                timestamp=change.time,
                source=source,
                source_record_id=str(change.pk),
                fingerprint=f"netbox-oc-{change.pk}",
                related_netbox_ip_id=change.changed_object_id if change.changed_object_id in live_ips else None,
                raw_data={
                    "prechange_data": change.prechange_data or {},
                    "postchange_data": change.postchange_data or {},
                    "object_repr": change.object_repr,
                },
            )
        )
    if not events:
        return []
    events = HistoricalIPEvent.objects.bulk_create(
        events,
        update_conflicts=True,
        unique_fields=["fingerprint"],
        update_fields=_UPSERT_FIELDS,
    )

    def index():
        from netbox.search.backends import search_backend

        search_backend.cache(events, remove_existing=True)

    transaction.on_commit(index)
    return events


@receiver(post_save, sender=ObjectChange, dispatch_uid="netbox_ip_history_objectchange")
def object_change_receiver(sender, instance, **kwargs):
    if instance.changed_object_type.model != "ipaddress":
        return
    if not get_plugin_config("netbox_ip_history", "enable_native_event_tracking"):
        return
    try:
        # Savepoint: a failure here must never break the IP change being logged.
        with transaction.atomic():
            record_object_changes([instance])
    except Exception:
        logger.warning("Failed to record ObjectChange %s as IP history", instance.pk, exc_info=True)


def backfill_native_events(batch_size=1000) -> int:
    """
    Record every ipaddress ObjectChange that is not yet stored as a native event.

    Already-recorded changes are skipped, so this is cheap to repeat. New events are added
    to NetBox's global search cache as they are written.
    """
    from .choices import SourceTypeChoices
    from .models import HistoricalIPEvent

    recorded = (
        HistoricalIPEvent.objects.filter(
            source__source_type=SourceTypeChoices.NETBOX, source_record_id__regex=r"^[0-9]+$"
        )
        .annotate(change_id=Cast("source_record_id", BigIntegerField()))
        .values("change_id")
    )
    pending = (
        ObjectChange.objects.filter(changed_object_type__model="ipaddress")
        .exclude(pk__in=recorded)
        .select_related("changed_object_type")
        .order_by("pk")
    )
    source, total, last_pk = None, 0, 0
    while batch := list(pending.filter(pk__gt=last_pk)[:batch_size]):
        source = source or get_native_source()
        total += len(record_object_changes(batch, source=source))
        last_pk = batch[-1].pk
    return total


@receiver(post_migrate, dispatch_uid="netbox_ip_history_backfill")
def backfill_after_migrate(sender, using=DEFAULT_DB_ALIAS, apps=None, verbosity=1, stdout=None, **kwargs):
    """Make NetBox history recorded before installation (or while tracking was off) visible after migrate."""
    if getattr(sender, "name", None) != "netbox_ip_history" or using != DEFAULT_DB_ALIAS:
        return
    if not (
        get_plugin_config("netbox_ip_history", "enable_native_event_tracking")
        and get_plugin_config("netbox_ip_history", "backfill_on_migrate")
    ):
        return
    try:
        if apps is not None:
            apps.get_model("netbox_ip_history", "HistoricalIPEvent")  # absent after "migrate ... zero"
    except LookupError:
        return
    try:
        recorded = backfill_native_events()
    except Exception:
        logger.warning("Backfilling native IP history after migrate failed", exc_info=True)
        return
    if recorded and verbosity and stdout is not None:
        stdout.write(f"  netbox_ip_history: recorded {recorded} existing NetBox IP change(s) as history events\n")
