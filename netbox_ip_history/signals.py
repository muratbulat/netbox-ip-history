import logging

logger = logging.getLogger("netbox.plugins.netbox_ip_history")

# Process-local cache for the singleton "netbox" ImportSource/ImportJob pair.
# get_or_create_netbox_source() is called once per real-time signal (cheap
# on its own) but also once per row from sync_netbox_ip_history's bulk
# resync loop, where re-running two get_or_create() SELECTs per row across
# potentially thousands of rows is a real, avoidable N+1. These records are
# effectively immutable system singletons once created, so caching them for
# the lifetime of the worker process is safe; if either is ever deleted out
# from under a cached reference, the next save() fails loudly (IntegrityError
# / DoesNotExist) rather than silently corrupting data.
_netbox_source_cache = {}


def get_or_create_netbox_source():
    """Retrieve or create the system NetBox ImportSource and default ImportJob."""
    cached = _netbox_source_cache.get("value")
    if cached is not None:
        return cached

    from .models import ImportJob, ImportSource

    source, _ = ImportSource.objects.get_or_create(
        slug="netbox",
        defaults={
            "name": "NetBox",
            "source_type": "netbox",
            "description": "Native NetBox IP lifecycle events",
            "enabled": True,
            "source_priority": 1,
        },
    )
    job, _ = ImportJob.objects.get_or_create(
        source=source,
        filename="native_netbox_sync",
        defaults={
            "status": "completed",
            "import_mode": "history_only",
            "dry_run": False,
        },
    )
    _netbox_source_cache["value"] = (source, job)
    return source, job


def record_object_change_as_event(change):
    """Convert a core.ObjectChange instance for ipaddress into a HistoricalIPEvent."""
    try:
        from netbox.plugins import get_plugin_config
        enabled = get_plugin_config("netbox_ip_history", "enable_native_event_tracking", True)
    except Exception:
        enabled = True

    if not enabled:
        return None

    if getattr(change, "changed_object_type", None) and change.changed_object_type.model != "ipaddress":
        return None

    from .choices import EventType
    from .models import HistoricalIPEvent
    from .services.timeline import (
        _guess_owner_type,
        classify_event_type,
        extract_ip_from_change,
        extract_netbox_change_details,
    )

    ip_str, prefix_len = extract_ip_from_change(change)
    if not ip_str:
        return None

    action = str(getattr(change, "action", "")).lower()
    pre = getattr(change, "prechange_data", {}) or {}
    post = getattr(change, "postchange_data", {}) or {}
    payloads = [post, pre]
    payload = next((p for p in payloads if p), {})
    details = extract_netbox_change_details(payload, change)
    pre_status = pre.get("status")
    post_status = post.get("status")
    if isinstance(pre_status, dict):
        pre_status = pre_status.get("label") or pre_status.get("value")
    if isinstance(post_status, dict):
        post_status = post_status.get("label") or post_status.get("value")

    user_str = str(getattr(change, "user_name", "") or "").lower()

    pre_details = extract_netbox_change_details(pre, change) if action == "update" and pre else {}
    post_details = extract_netbox_change_details(post, change) if action == "update" and post else {}

    event_type = classify_event_type(
        action, user_str,
        pre_payload=pre, post_payload=post,
        pre_details=pre_details, post_details=post_details,
        pre_status=pre_status, post_status=post_status,
    ) or EventType.UPDATED

    tenant_name = payload.get("tenant") or ""
    if isinstance(tenant_name, dict):
        tenant_name = tenant_name.get("name") or ""

    source, job = get_or_create_netbox_source()
    fingerprint = f"netbox-oc-{change.pk}"

    event, _ = HistoricalIPEvent.objects.update_or_create(
        fingerprint=fingerprint,
        defaults={
            "timestamp": change.time,
            "ip_address": ip_str,
            "prefix_length": prefix_len,
            "vrf_name": details["vrf_name"] or "Global",
            "tenant_name": str(tenant_name) if tenant_name else "",
            "event_type": event_type,
            "source": source,
            "source_record_id": str(change.pk),
            "source_event_type": action,
            "source_username": getattr(change, "user_name", "") or "",
            "hostname": details["dns_name"] or details["host_name"],
            "dns_name": details["dns_name"],
            "description": details["description"],
            "owner_name": details["host_name"],
            "owner_type": _guess_owner_type(payload),
            "interface_name": details["interface_name"],
            "status": details["status"],
            "import_job": job,
            "raw_data": {
                "prechange_data": change.prechange_data or {},
                "postchange_data": change.postchange_data or {},
                "object_repr": change.object_repr,
            },
        },
    )
    return event


def object_change_receiver(sender, instance, created, **kwargs):
    """Signal handler for core.models.ObjectChange."""
    try:
        if getattr(instance, "changed_object_type", None) and instance.changed_object_type.model == "ipaddress":
            record_object_change_as_event(instance)
    except Exception:
        # Native IP lifecycle tracking failing silently is exactly the kind
        # of regression that must be visible: DEBUG is filtered out of most
        # production logging configs, so a real bug here (as opposed to a
        # single malformed ObjectChange) could stop tracking indefinitely
        # with no operator ever seeing it. warning + traceback ensures it
        # shows up in NetBox's default logs without raising into the
        # request/save path that triggered this signal.
        logger.warning("Failed to record native ObjectChange to IP history", exc_info=True)


def connect_signals():
    """Connect signal listeners if running in a full NetBox environment."""
    try:
        from django.db.models.signals import post_save
        from core.models import ObjectChange
        post_save.connect(object_change_receiver, sender=ObjectChange, dispatch_uid="netbox_ip_history_objectchange")
    except Exception:
        pass
