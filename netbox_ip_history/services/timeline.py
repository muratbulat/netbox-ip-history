"""
Timeline assembly and NetBox ObjectChange interpretation.

``ObjectLookup`` resolves every NetBox object referenced by a batch of ObjectChange
payloads with a fixed number of queries (no per-row lookups), so rendering a timeline
costs O(1) queries regardless of how many events it contains. Pass ``resolve=False`` to
interpret payloads purely from their own content (e.g. changelog exports from another
NetBox instance, whose object IDs mean nothing locally).
"""

from collections.abc import Iterable
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.db.models.functions import Lower

from ..choices import EventTypeChoices, SourceTypeChoices
from ..models import GLOBAL_VRF, HistoricalIPEvent
from .normalize import RecordError, normalize_ip

__all__ = (
    "ObjectLookup",
    "change_details",
    "classify_event_type",
    "compare_sources",
    "describe_change",
    "extract_ip_from_change",
    "get_timeline",
    "native_events",
    "owner_type",
    "resolve_assigned_object_type",
)

INTERFACE = "interface"
VMINTERFACE = "vminterface"
FHRPGROUP = "fhrpgroup"
_OWNER_TYPES = {INTERFACE: "device", VMINTERFACE: "virtualmachine", FHRPGROUP: "fhrpgroup"}
_EVENT_LABELS = {value: label for value, label, *_ in EventTypeChoices.CHOICES}


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _name(value) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("display") or "")
    return value if isinstance(value, str) else ""


def _split_repr(text: str) -> tuple[str, str]:
    """Split NetBox interface representations ("host > iface" / "host: iface")."""
    text = str(text or "").strip()
    for separator in (" > ", ": "):
        if separator in text:
            host, iface = text.split(separator, 1)
            return host.strip(), iface.strip()
    return "", text


def status_label(value) -> str:
    if isinstance(value, dict):
        return str(value.get("label") or value.get("value") or "")
    return str(value or "")


def extract_ip_from_change(change) -> tuple[str | None, int | None]:
    """Return the canonical (ip, prefix_length) an ipaddress ObjectChange refers to."""
    candidates = [
        payload.get("address")
        for payload in (_get(change, "postchange_data"), _get(change, "prechange_data"))
        if isinstance(payload, dict) and payload.get("address")
    ]
    candidates.append(_get(change, "object_repr"))
    for value in candidates:
        if not value:
            continue
        try:
            return normalize_ip(value)
        except RecordError:
            continue
    return None, None


class ObjectLookup:
    """Batch resolver for object IDs referenced by ObjectChange payloads."""

    def __init__(self, payloads: Iterable[dict] = (), resolve: bool = True):
        self.resolve = resolve
        self.content_types: dict[int, str] = {}
        self.interfaces: dict[int, tuple[str, str]] = {}
        self.vminterfaces: dict[int, tuple[str, str]] = {}
        self.devices: dict[int, str] = {}
        self.virtual_machines: dict[int, str] = {}
        self.vrfs: dict[int, str] = {}
        self.device_names: set[str] = set()
        self.vm_names: set[str] = set()
        if resolve:
            self._prefetch([p for p in payloads if isinstance(p, dict)])

    def _prefetch(self, payloads: list[dict]) -> None:
        from core.models import ObjectChange
        from dcim.models import Device, Interface
        from ipam.models import VRF
        from virtualization.models import VirtualMachine, VMInterface

        ct_ids, assigned, devices, vms, vrfs = set(), set(), set(), set(), set()
        for payload in payloads:
            for key in ("assigned_object_type", "assigned_object_type_id"):
                if isinstance(payload.get(key), int):
                    ct_ids.add(payload[key])
            if isinstance(payload.get("assigned_object_id"), int):
                assigned.add(payload["assigned_object_id"])
            for key, bucket in (("device", devices), ("host", devices), ("virtual_machine", vms), ("vrf", vrfs)):
                if isinstance(payload.get(key), int):
                    bucket.add(payload[key])

        if ct_ids:
            self.content_types = {ct.pk: ct.model for ct in ContentType.objects.filter(pk__in=ct_ids)}
        if assigned:
            self.interfaces = {
                pk: (dev or "", name)
                for pk, dev, name in Interface.objects.filter(pk__in=assigned).values_list("pk", "device__name", "name")
            }
            self.vminterfaces = {
                pk: (vm or "", name)
                for pk, vm, name in VMInterface.objects.filter(pk__in=assigned).values_list(
                    "pk", "virtual_machine__name", "name"
                )
            }
            # Interfaces deleted since the change: fall back to their own last changelog entry.
            # Intersection, not union: dcim and virtualization interface PKs overlap, so an ID
            # found in one table may still be a deleted object of the other type. Each changelog
            # row only fills its own model's table, and only where that table has no entry.
            missing = assigned - (self.interfaces.keys() & self.vminterfaces.keys())
            if missing:
                last_changes = (
                    ObjectChange.objects.filter(
                        changed_object_type__model__in=(INTERFACE, VMINTERFACE), changed_object_id__in=missing
                    )
                    .order_by("changed_object_type_id", "changed_object_id", "-time")
                    .distinct("changed_object_type_id", "changed_object_id")
                    .values_list("changed_object_type__model", "changed_object_id", "object_repr")
                )
                for model, pk, object_repr in last_changes:
                    target = self.interfaces if model == INTERFACE else self.vminterfaces
                    target.setdefault(pk, _split_repr(object_repr))
        if devices:
            self.devices = dict(Device.objects.filter(pk__in=devices).values_list("pk", "name"))
        if vms:
            self.virtual_machines = dict(VirtualMachine.objects.filter(pk__in=vms).values_list("pk", "name"))
        if vrfs:
            self.vrfs = dict(VRF.objects.filter(pk__in=vrfs).values_list("pk", "name"))

        names = set()
        for payload in payloads:
            details = _raw_details(payload, self)
            names.update(n.lower() for n in (details["dns_name"], details["host_name"]) if n)
        if names:
            self.device_names = set(
                Device.objects.annotate(lname=Lower("name")).filter(lname__in=names).values_list("lname", flat=True)
            )
            self.vm_names = set(
                VirtualMachine.objects.annotate(lname=Lower("name"))
                .filter(lname__in=names)
                .values_list("lname", flat=True)
            )

    def is_device(self, name: str) -> bool:
        return bool(name) and name.lower() in self.device_names

    def is_vm(self, name: str) -> bool:
        return bool(name) and name.lower() in self.vm_names


def _type_from_text(text: str) -> str | None:
    text = text.lower()
    if "vminterface" in text or "vm interface" in text or "virtualization" in text:
        return VMINTERFACE
    if "fhrp" in text:
        return FHRPGROUP
    if "interface" in text or "dcim" in text:
        return INTERFACE
    return None


def resolve_assigned_object_type(
    payload, lookup: ObjectLookup | None = None, change=None, hint: str = ""
) -> str | None:
    """Return 'interface', 'vminterface', 'fhrpgroup' or None for an ipaddress payload."""
    if not isinstance(payload, dict):
        return None
    lookup = lookup or ObjectLookup(resolve=False)

    for key in ("assigned_object_type", "assigned_object_type_id"):
        value = payload.get(key)
        if isinstance(value, int) and value in lookup.content_types:
            resolved = _type_from_text(lookup.content_types[value])
            if resolved:
                return resolved
        elif isinstance(value, dict):
            resolved = _type_from_text(f"{value.get('app_label', '')} {value.get('model') or value.get('name') or ''}")
            if resolved:
                return resolved
        elif isinstance(value, str) and value:
            resolved = _type_from_text(value)
            if resolved:
                return resolved

    assigned = payload.get("assigned_object")
    if isinstance(assigned, dict):
        url = str(assigned.get("url") or "").lower()
        if "/virtualization/interfaces/" in url:
            return VMINTERFACE
        if "/dcim/interfaces/" in url:
            return INTERFACE
        if "/fhrp-groups/" in url:
            return FHRPGROUP
        if "device" in assigned:
            return INTERFACE
        if "virtual_machine" in assigned:
            return VMINTERFACE

    if "device" in payload and "virtual_machine" not in payload:
        return INTERFACE
    if "virtual_machine" in payload and "device" not in payload:
        return VMINTERFACE

    if change is not None:
        for other in (_get(change, "prechange_data"), _get(change, "postchange_data")):
            if isinstance(other, dict) and other is not payload:
                resolved = resolve_assigned_object_type(other, lookup)
                if resolved:
                    return resolved

    assigned_id = payload.get("assigned_object_id")
    if assigned_id and hint:
        hint = hint.lower()
        if lookup.interfaces.get(assigned_id, ("", ""))[0].lower() == hint:
            return INTERFACE
        if lookup.vminterfaces.get(assigned_id, ("", ""))[0].lower() == hint:
            return VMINTERFACE
    return None


def _raw_details(payload: dict, lookup: ObjectLookup, change=None) -> dict[str, str]:
    """Host/interface/DNS/VRF/status from a payload, before name-based disambiguation."""
    host, iface = "", ""
    dns_name = str(payload.get("dns_name") or payload.get("hostname") or "")

    assigned = payload.get("assigned_object")
    if isinstance(assigned, dict):
        iface = _name(assigned)
        for key, table in (("virtual_machine", lookup.virtual_machines), ("device", lookup.devices)):
            value = assigned.get(key)
            host = (table.get(value, "") if isinstance(value, int) else _name(value)) or host
        if not host:
            host = _name(assigned.get("parent"))
    elif isinstance(assigned, str) and assigned:
        host, iface = _split_repr(assigned)

    if not host:
        for key in ("virtual_machine", "device", "host", "hostname", "server"):
            value = payload.get(key)
            if isinstance(value, int):
                table = lookup.virtual_machines if key in ("virtual_machine", "server") else lookup.devices
                value = table.get(value, "")
            host = _name(value)
            if host:
                break
    if not iface:
        iface = next((_name(payload.get(k)) for k in ("interface", "vminterface", "port") if _name(payload.get(k))), "")

    assigned_id = payload.get("assigned_object_id")
    if assigned_id and (not host or not iface):
        target = resolve_assigned_object_type(payload, lookup, change, hint=dns_name)
        if target is None and lookup.is_device(dns_name):
            target = INTERFACE
        candidates = {
            INTERFACE: [lookup.interfaces],
            VMINTERFACE: [lookup.vminterfaces],
            None: [lookup.interfaces, lookup.vminterfaces],
        }.get(target, [])
        for table in candidates:
            if assigned_id in table:
                owner, name = table[assigned_id]
                host, iface = host or owner, iface or name
                if host:
                    break

    vrf = payload.get("vrf")
    if isinstance(vrf, dict):
        vrf_name = str(vrf.get("name") or vrf.get("rd") or vrf.get("display") or "")
    elif isinstance(vrf, int):
        vrf_name = lookup.vrfs.get(vrf, "")
    else:
        vrf_name = vrf if isinstance(vrf, str) else ""
    if vrf_name.lower() == GLOBAL_VRF.lower():
        vrf_name = ""

    return {
        "host_name": host,
        "interface_name": iface,
        "dns_name": dns_name,
        "description": str(payload.get("description") or payload.get("comments") or ""),
        "vrf_name": vrf_name,
        "status": status_label(payload.get("status")),
    }


def change_details(payload, lookup: ObjectLookup | None = None, change=None) -> dict[str, str]:
    """
    Interpret one ipaddress ObjectChange payload.

    When the IP's DNS name is a known Device (or VM) but the resolved owner is not, the DNS
    name wins: interface IDs are reused across dcim/virtualization, so a stale or ambiguous
    ID must not attach the address to the wrong kind of object.
    """
    if not isinstance(payload, dict):
        payload = {}
    lookup = lookup or ObjectLookup(resolve=False)
    details = _raw_details(payload, lookup, change)
    dns_name, host = details["dns_name"], details["host_name"]
    if dns_name and host and host.lower() != dns_name.lower():
        if lookup.is_device(dns_name):
            prefer_dns = lookup.is_vm(host) or not lookup.is_device(host)
        else:
            prefer_dns = lookup.is_vm(dns_name) and (lookup.is_device(host) or not lookup.is_vm(host))
        if prefer_dns:
            details["host_name"] = dns_name
    elif dns_name and not host and (lookup.is_device(dns_name) or lookup.is_vm(dns_name)):
        details["host_name"] = dns_name
    return details


def owner_type(payload, lookup: ObjectLookup | None = None) -> str:
    """'device', 'virtualmachine', 'fhrpgroup' or '' (unknown) for the payload's assignment."""
    return _OWNER_TYPES.get(resolve_assigned_object_type(payload, lookup), "")


def classify_event_type(
    action,
    user_str="",
    pre_payload=None,
    post_payload=None,
    pre_details=None,
    post_details=None,
    pre_status=None,
    post_status=None,
    lookup: ObjectLookup | None = None,
):
    """
    Most specific EventType for an ObjectChange action, or None for unknown actions.

    Updates are ranked: status change, then (un/re)assignment and owner-type change, then
    interface, DNS name and hostname changes, falling back to UPDATED.
    """
    action = str(action or "").lower()
    if action == "create":
        if any(hint in str(user_str or "").lower() for hint in ("ping", "discover", "scan")):
            return EventTypeChoices.DISCOVERED
        return EventTypeChoices.CREATED
    if action == "delete":
        return EventTypeChoices.DELETED
    if action != "update":
        return None

    if pre_status and post_status and str(pre_status).lower() != str(post_status).lower():
        return EventTypeChoices.STATUS_CHANGED

    pre_details, post_details = pre_details or {}, post_details or {}

    def field(details, key):
        return str(details.get(key) or "").strip()

    pre_host, post_host = field(pre_details, "host_name"), field(post_details, "host_name")
    if pre_host.lower() != post_host.lower():
        if not pre_host:
            return EventTypeChoices.ASSIGNED
        if not post_host:
            return EventTypeChoices.UNASSIGNED
        pre_type, post_type = owner_type(pre_payload, lookup), owner_type(post_payload, lookup)
        if pre_type and post_type and pre_type != post_type:
            return EventTypeChoices.OWNER_CHANGED
        return EventTypeChoices.REASSIGNED

    pre_iface, post_iface = field(pre_details, "interface_name"), field(post_details, "interface_name")
    if pre_host and pre_iface.lower() != post_iface.lower():
        return EventTypeChoices.INTERFACE_CHANGED

    pre_dns, post_dns = field(pre_details, "dns_name"), field(post_details, "dns_name")
    if pre_dns.lower() != post_dns.lower():
        return EventTypeChoices.DNS_CHANGED

    pre_hostname = str((pre_payload or {}).get("hostname") or "").strip()
    post_hostname = str((post_payload or {}).get("hostname") or "").strip()
    if pre_hostname.lower() != post_hostname.lower():
        return EventTypeChoices.HOSTNAME_CHANGED

    return EventTypeChoices.UPDATED


def _action(change) -> str:
    action = _get(change, "action")
    if isinstance(action, dict):
        action = action.get("value")
    return str(action or "").lower()


def describe_change(change, lookup: ObjectLookup | None = None) -> dict[str, Any] | None:
    """
    Normalized event fields for an ipaddress ObjectChange (model instance or dict), or None
    if no IP address can be determined.
    """
    ip, prefix_length = extract_ip_from_change(change)
    if not ip:
        return None
    lookup = lookup or ObjectLookup(resolve=False)
    pre = _get(change, "prechange_data") or {}
    post = _get(change, "postchange_data") or {}
    pre = pre if isinstance(pre, dict) else {}
    post = post if isinstance(post, dict) else {}
    payload = post or pre
    action = _action(change)
    details = change_details(payload, lookup, change)
    is_update = action == "update"
    username = str(_get(change, "user_name") or "")
    event_type = classify_event_type(
        action,
        username,
        pre_payload=pre,
        post_payload=post,
        pre_details=change_details(pre, lookup, change) if is_update and pre else {},
        post_details=change_details(post, lookup, change) if is_update and post else {},
        pre_status=status_label(pre.get("status")),
        post_status=status_label(post.get("status")),
        lookup=lookup,
    ) or EventTypeChoices.UPDATED
    tenant = payload.get("tenant")
    return {
        "ip_address": ip,
        "prefix_length": prefix_length,
        "event_type": event_type,
        "source_event_type": action,
        "source_username": username,
        "vrf_name": details["vrf_name"],
        "tenant_name": _name(tenant) if not isinstance(tenant, int) else "",
        "hostname": details["dns_name"] or details["host_name"],
        "dns_name": details["dns_name"],
        "description": details["description"],
        "owner_name": details["host_name"],
        "owner_type": owner_type(payload, lookup),
        "interface_name": details["interface_name"],
        "status": details["status"],
    }


def _matches(entry: dict, vrf: str, event_type: str, owner: str, vrf_exact: bool = False) -> bool:
    if vrf:
        wanted, actual = vrf.lower(), entry["vrf"].lower()
        if wanted == GLOBAL_VRF.lower():
            matched = actual == GLOBAL_VRF.lower()
        else:
            matched = wanted == actual if vrf_exact else wanted in actual
        if not matched:
            return False
    if event_type and entry["event_type"] != event_type:
        return False
    if owner:
        haystack = " ".join(str(entry.get(k) or "") for k in ("owner_name", "hostname", "dns_name")).lower()
        if owner.lower() not in haystack:
            return False
    return True


def _entry_from_event(event: HistoricalIPEvent) -> dict[str, Any]:
    return {
        "pk": event.pk,
        "kind": "event",
        "url": event.get_absolute_url(),
        "timestamp": event.timestamp,
        "event_type": event.event_type,
        "event_type_display": event.get_event_type_display(),
        "color": event.get_event_type_color(),
        "source": event.source.name,
        "native": event.source.source_type == SourceTypeChoices.NETBOX,
        "ip_address": event.ip_address,
        "vrf": event.scope,
        "owner_type": event.owner_type,
        "owner_name": event.owner_name or event.device_name or event.virtual_machine_name or event.hostname,
        "interface_name": event.interface_name,
        "hostname": event.hostname,
        "dns_name": event.dns_name,
        "mac_address": event.mac_address,
        "status": event.status,
        "description": event.description,
        "username": event.source_username,
    }


def native_events(ip_address, user=None, date_from=None, date_to=None, username="", exclude_pks=()):
    """
    Timeline entries read live from core.ObjectChange for an IP, covering changes made before
    the plugin was installed (or while native tracking was disabled).
    """
    from core.models import ObjectChange

    try:
        canonical_ip, _ = normalize_ip(ip_address)
    except RecordError:
        return []
    if user is not None and not user.has_perm("core.view_objectchange"):
        return []

    queryset = ObjectChange.objects.all() if user is None else ObjectChange.objects.restrict(user, "view")
    # Exact-or-"<ip>/" prefix match in SQL; the canonical comparison below is authoritative.
    ip_filter = Q()
    for field in ("postchange_data__address", "prechange_data__address", "object_repr"):
        ip_filter |= Q(**{field: canonical_ip}) | Q(**{f"{field}__startswith": f"{canonical_ip}/"})
    queryset = queryset.filter(changed_object_type__model="ipaddress").filter(ip_filter).order_by("-time")
    if date_from:
        queryset = queryset.filter(time__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(time__date__lte=date_to)
    if username:
        queryset = queryset.filter(user_name__icontains=username)
    if exclude_pks:
        queryset = queryset.exclude(pk__in=exclude_pks)

    changes = [c for c in queryset if extract_ip_from_change(c)[0] == canonical_ip]
    lookup = ObjectLookup(
        payload for change in changes for payload in (change.prechange_data, change.postchange_data)
    )
    entries = []
    for change in changes:
        fields = describe_change(change, lookup)
        entries.append({
            "pk": change.pk,
            "kind": "objectchange",
            "url": change.get_absolute_url(),
            "timestamp": change.time,
            "event_type": fields["event_type"],
            "event_type_display": _EVENT_LABELS.get(fields["event_type"], fields["event_type"]),
            "color": EventTypeChoices.colors.get(fields["event_type"]),
            "source": "NetBox",
            "native": True,
            "ip_address": canonical_ip,
            "vrf": fields["vrf_name"] or GLOBAL_VRF,
            "owner_type": fields["owner_type"],
            "owner_name": fields["owner_name"],
            "interface_name": fields["interface_name"],
            "hostname": fields["hostname"],
            "dns_name": fields["dns_name"],
            "mac_address": "",
            "status": fields["status"],
            "description": fields["description"],
            "username": fields["source_username"],
        })
    return entries


def get_timeline(
    ip_address,
    vrf="",
    source="",
    event_type="",
    oldest_first=False,
    date_from=None,
    date_to=None,
    owner="",
    username="",
    user=None,
    vrf_exact=False,
):
    """
    Merged, sorted timeline for one IP address: stored HistoricalIPEvents plus native
    ObjectChanges not yet recorded as events. Invalid IPs yield an empty timeline.

    ``vrf="Global"`` matches events outside any VRF, however the source recorded that. Other
    ``vrf`` values match VRF names or RDs as a substring, or exactly with ``vrf_exact``.
    When ``user`` is given, results are restricted to objects the user may view.
    """
    try:
        canonical_ip, _ = normalize_ip(ip_address)
    except RecordError:
        return []

    queryset = HistoricalIPEvent.objects.all() if user is None else HistoricalIPEvent.objects.restrict(user, "view")
    queryset = queryset.filter(ip_address=canonical_ip).select_related("source")
    if vrf.lower() == GLOBAL_VRF.lower():
        queryset = queryset.filter((Q(vrf_name="") | Q(vrf_name__iexact=GLOBAL_VRF)) & Q(vrf_rd=""))
    elif vrf and vrf_exact:
        queryset = queryset.filter(Q(vrf_name__iexact=vrf) | Q(vrf_rd__iexact=vrf))
    elif vrf:
        queryset = queryset.filter(Q(vrf_name__icontains=vrf) | Q(vrf_rd__icontains=vrf))
    if source:
        queryset = queryset.filter(Q(source__slug__icontains=source) | Q(source__name__icontains=source))
    if event_type:
        queryset = queryset.filter(event_type=event_type)
    if date_from:
        queryset = queryset.filter(timestamp__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(timestamp__date__lte=date_to)
    if owner:
        queryset = queryset.filter(
            Q(owner_name__icontains=owner)
            | Q(hostname__icontains=owner)
            | Q(device_name__icontains=owner)
            | Q(virtual_machine_name__icontains=owner)
        )
    if username:
        queryset = queryset.filter(source_username__icontains=username)

    events = list(queryset)
    entries = [_entry_from_event(event) for event in events]

    if not source or source.lower() in "netbox":
        recorded = _recorded_change_ids(canonical_ip)
        entries.extend(
            entry
            for entry in native_events(
                canonical_ip, user=user, date_from=date_from, date_to=date_to, username=username, exclude_pks=recorded
            )
            if _matches(entry, vrf, event_type, owner, vrf_exact)
        )

    entries.sort(key=lambda entry: entry["timestamp"], reverse=not oldest_first)
    return entries


def _recorded_change_ids(canonical_ip: str) -> list[int]:
    """ObjectChange PKs already stored as native events for this IP (regardless of user scope)."""
    values = HistoricalIPEvent.objects.filter(
        ip_address=canonical_ip, source__source_type=SourceTypeChoices.NETBOX
    ).values_list("source_record_id", flat=True)
    return [int(value) for value in values if str(value).isdigit()]


def compare_sources(ip_address, user=None) -> list[dict[str, Any]]:
    """Latest known state of an IP according to each source (NetBox first)."""
    entries = get_timeline(ip_address, user=user)
    latest: dict[str, dict] = {}
    for entry in entries:  # newest first
        latest.setdefault("NetBox" if entry["native"] else entry["source"], entry)
    rows = [
        {
            "source": name,
            "native": entry["native"],
            "hostname": entry["hostname"],
            "owner": entry["owner_name"],
            "dns_name": entry["dns_name"],
            "mac_address": entry["mac_address"],
            "vrf": entry["vrf"],
            "status": entry["status"],
            "event_type": entry["event_type"],
            "last_seen": entry["timestamp"],
        }
        for name, entry in latest.items()
    ]
    rows.sort(key=lambda row: (not row["native"], row["source"].lower()))
    return rows
