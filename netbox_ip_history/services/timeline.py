try:
    from django.db.models import Q
except ImportError:
    class _MockQ:
        """No-op stand-in for django.db.models.Q when Django isn't
        installed (the Django-optional pattern used throughout this
        module). Stores its args/kwargs — unlike a pure no-op — purely so
        tests can introspect what filter was *constructed* via repr()/str()
        even though it can't actually be evaluated without a real ORM."""
        def __init__(self, *args, **kwargs):
            self.children = list(args) + [(k, v) for k, v in kwargs.items()]
        def __or__(self, other):
            combined = _MockQ()
            combined.children = self.children + getattr(other, "children", [])
            return combined
        def __and__(self, other):
            combined = _MockQ()
            combined.children = self.children + getattr(other, "children", [])
            return combined
        def __repr__(self):
            return f"<Q: {self.children!r}>"
    Q = _MockQ

from ..choices import EventType
from ..models import HistoricalIPEvent


def extract_ip_from_change(change):
    """
    Extract the canonical IP string and prefix length from a NetBox ObjectChange for an IPAddress object.
    Returns (canonical_ip, prefix_length) or (None, None).
    """
    from .normalize import normalize_ip

    # Check postchange_data first, then prechange_data
    for payload in (getattr(change, "postchange_data", None), getattr(change, "prechange_data", None)):
        if isinstance(payload, dict) and payload.get("address"):
            raw_addr = str(payload["address"]).strip()
            try:
                return normalize_ip(raw_addr)
            except Exception:
                ip_part = raw_addr.split("/")[0].strip()
                prefix = int(raw_addr.split("/")[1]) if "/" in raw_addr and raw_addr.split("/")[1].isdigit() else None
                return ip_part, prefix

    # Fallback to object_repr (e.g. "172.17.8.8/24")
    repr_str = str(getattr(change, "object_repr", "") or "").strip()
    if repr_str:
        try:
            return normalize_ip(repr_str)
        except Exception:
            ip_part = repr_str.split("/")[0].strip()
            prefix = int(repr_str.split("/")[1]) if "/" in repr_str and repr_str.split("/")[1].isdigit() else None
            return ip_part, prefix

    return None, None


def resolve_assigned_object_type(payload, change=None, hint_name=""):
    """
    Determine whether the assigned object is a dcim.interface, virtualization.vminterface, or other.
    Inspects assigned_object_type (dict, str, int/FK), assigned_object_type_id, assigned_object dict/url,
    and cross-checks with DNS/hostname hints against live models.
    """
    # 1. Check assigned_object_type in payload
    obj_type = payload.get("assigned_object_type")
    if isinstance(obj_type, int):
        try:
            from django.contrib.contenttypes.models import ContentType
            ct = ContentType.objects.filter(pk=obj_type).first()
            if ct:
                if ct.model in ("vminterface", "interface", "fhrpgroup"):
                    return ct.model
                if "vm" in ct.model:
                    return "vminterface"
                if "interface" in ct.model:
                    return "interface"
        except Exception:
            pass
    elif isinstance(obj_type, dict):
        model_name = (obj_type.get("model") or obj_type.get("name") or "").lower()
        app_label = (obj_type.get("app_label") or "").lower()
        if "vminterface" in model_name or "virtualization" in app_label:
            return "vminterface"
        if "interface" in model_name or "dcim" in app_label:
            return "interface"
        if "fhrp" in model_name:
            return "fhrpgroup"
    elif isinstance(obj_type, str) and obj_type:
        lower = obj_type.lower()
        if "vminterface" in lower or "vm interface" in lower or "virtualization" in lower:
            return "vminterface"
        if "interface" in lower or "dcim" in lower:
            return "interface"
        if "fhrp" in lower:
            return "fhrpgroup"

    # 2. Check assigned_object_type_id
    obj_type_id = payload.get("assigned_object_type_id")
    if isinstance(obj_type_id, int):
        try:
            from django.contrib.contenttypes.models import ContentType
            ct = ContentType.objects.filter(pk=obj_type_id).first()
            if ct:
                if ct.model in ("vminterface", "interface", "fhrpgroup"):
                    return ct.model
                if "vm" in ct.model:
                    return "vminterface"
                if "interface" in ct.model:
                    return "interface"
        except Exception:
            pass

    # 3. Check assigned_object dict structure and REST URL
    assigned = payload.get("assigned_object")
    if isinstance(assigned, dict):
        url = (assigned.get("url") or "").lower()
        if "/dcim/interfaces/" in url or "/api/dcim/" in url:
            return "interface"
        if "/virtualization/interfaces/" in url or "/api/virtualization/" in url:
            return "vminterface"
        if "/fhrp-groups/" in url:
            return "fhrpgroup"
        if "device" in assigned:
            return "interface"
        if "virtual_machine" in assigned:
            return "vminterface"

    # 4. Check direct payload fields
    if "device" in payload and "virtual_machine" not in payload:
        return "interface"
    if "virtual_machine" in payload and "device" not in payload:
        return "vminterface"

    # 5. Check prechange_data / postchange_data on change if provided
    if change:
        for p in (getattr(change, "prechange_data", None), getattr(change, "postchange_data", None)):
            if isinstance(p, dict) and p != payload:
                resolved = resolve_assigned_object_type(p)
                if resolved:
                    return resolved

    # 6. Check hint_name (DNS / Hostname) against live database ownership of assigned_id
    assigned_id = payload.get("assigned_object_id")
    if assigned_id and hint_name:
        try:
            from dcim.models import Interface
            if Interface.objects.filter(pk=assigned_id, device__name__iexact=hint_name).exists():
                return "interface"
        except Exception:
            pass
        try:
            from virtualization.models import VMInterface
            if VMInterface.objects.filter(pk=assigned_id, virtual_machine__name__iexact=hint_name).exists():
                return "vminterface"
        except Exception:
            pass

    return None


def extract_netbox_change_details(payload, change=None):
    """
    Extract host, interface, dns, vrf, description, and status from NetBox ObjectChange snapshots.
    Supports NetBox 3.x, 4.x nested dicts, string representations, and ID resolution.
    """
    host_name = ""
    interface_name = ""
    dns_name = payload.get("dns_name") or payload.get("hostname") or ""
    description = payload.get("description") or payload.get("comments") or ""

    # 1. Check assigned_object in payload
    assigned = payload.get("assigned_object")
    if isinstance(assigned, dict):
        interface_name = assigned.get("name") or assigned.get("display") or ""
        vm = assigned.get("virtual_machine")
        if isinstance(vm, dict):
            host_name = vm.get("name") or vm.get("display") or ""
        elif isinstance(vm, str) and vm:
            host_name = vm
        elif isinstance(vm, int) and vm:
            try:
                from virtualization.models import VirtualMachine
                vm_obj = VirtualMachine.objects.filter(pk=vm).first()
                if vm_obj:
                    host_name = vm_obj.name
            except Exception:
                pass

        dev = assigned.get("device")
        if isinstance(dev, dict):
            host_name = dev.get("name") or dev.get("display") or ""
        elif isinstance(dev, str) and dev:
            host_name = dev
        elif isinstance(dev, int) and dev:
            try:
                from dcim.models import Device
                dev_obj = Device.objects.filter(pk=dev).first()
                if dev_obj:
                    host_name = dev_obj.name
            except Exception:
                pass

        parent = assigned.get("parent")
        if isinstance(parent, dict) and not host_name:
            host_name = parent.get("name") or parent.get("display") or ""
        elif isinstance(parent, str) and parent and not host_name:
            host_name = parent
    elif isinstance(assigned, str) and assigned:
        if " > " in assigned:
            parts = assigned.split(" > ", 1)
            host_name = parts[0].strip()
            interface_name = parts[1].strip()
        elif ": " in assigned:
            parts = assigned.split(": ", 1)
            host_name = parts[0].strip()
            interface_name = parts[1].strip()
        else:
            interface_name = assigned.strip()

    # 2. Check direct fields
    if not host_name:
        for f in ("virtual_machine", "device", "host", "hostname", "server"):
            val = payload.get(f)
            if isinstance(val, dict):
                host_name = val.get("name") or val.get("display") or ""
                if host_name:
                    break
            elif isinstance(val, str) and val:
                host_name = val
                break
            elif isinstance(val, int) and val:
                if f in ("virtual_machine", "server"):
                    try:
                        from virtualization.models import VirtualMachine
                        vm_obj = VirtualMachine.objects.filter(pk=val).first()
                        if vm_obj:
                            host_name = vm_obj.name
                            break
                    except Exception:
                        pass
                elif f in ("device", "host"):
                    try:
                        from dcim.models import Device
                        dev_obj = Device.objects.filter(pk=val).first()
                        if dev_obj:
                            host_name = dev_obj.name
                            break
                    except Exception:
                        pass

    if not interface_name:
        for f in ("interface", "vminterface", "port"):
            val = payload.get(f)
            if isinstance(val, dict):
                interface_name = val.get("name") or val.get("display") or ""
                if interface_name:
                    break
            elif isinstance(val, str) and val:
                interface_name = val
                break

    # 3. Check assigned_object_id and assigned_object_type resolution
    assigned_id = payload.get("assigned_object_id")
    if assigned_id and (not host_name or not interface_name):
        target_model = resolve_assigned_object_type(payload, change, hint_name=dns_name)

        # If it's a device interface (dcim.interface)
        if target_model == "interface":
            try:
                from dcim.models import Interface
                inf = Interface.objects.filter(pk=assigned_id).select_related("device").first()
                if inf:
                    host_name = host_name or getattr(inf.device, "name", "")
                    interface_name = interface_name or inf.name
            except Exception:
                pass

            if not host_name or not interface_name:
                try:
                    from core.models import ObjectChange
                    inf_change = ObjectChange.objects.filter(
                        changed_object_id=assigned_id,
                        changed_object_type__model="interface"
                    ).order_by("-time").first()
                    if inf_change:
                        repr_str = str(inf_change.object_repr or "")
                        if " > " in repr_str:
                            parts = repr_str.split(" > ", 1)
                            host_name = host_name or parts[0].strip()
                            interface_name = interface_name or parts[1].strip()
                        elif ": " in repr_str:
                            parts = repr_str.split(": ", 1)
                            host_name = host_name or parts[0].strip()
                            interface_name = interface_name or parts[1].strip()
                        else:
                            interface_name = interface_name or repr_str.strip()

                        if not host_name:
                            inf_payload = inf_change.postchange_data or inf_change.prechange_data or {}
                            if isinstance(inf_payload, dict):
                                dev_val = inf_payload.get("device")
                                if isinstance(dev_val, dict):
                                    host_name = host_name or dev_val.get("name") or dev_val.get("display") or ""
                                elif isinstance(dev_val, str) and dev_val:
                                    host_name = host_name or dev_val
                                elif isinstance(dev_val, int) and dev_val:
                                    try:
                                        from dcim.models import Device
                                        d_obj = Device.objects.filter(pk=dev_val).first()
                                        if d_obj:
                                            host_name = host_name or d_obj.name
                                    except Exception:
                                        pass
                except Exception:
                    pass

        # If it's a VM interface (virtualization.vminterface)
        elif target_model == "vminterface":
            try:
                from virtualization.models import VMInterface
                vminf = VMInterface.objects.filter(pk=assigned_id).select_related("virtual_machine").first()
                if vminf:
                    host_name = host_name or getattr(vminf.virtual_machine, "name", "")
                    interface_name = interface_name or vminf.name
            except Exception:
                pass

            if not host_name or not interface_name:
                try:
                    from core.models import ObjectChange
                    inf_change = ObjectChange.objects.filter(
                        changed_object_id=assigned_id,
                        changed_object_type__model="vminterface"
                    ).order_by("-time").first()
                    if inf_change:
                        repr_str = str(inf_change.object_repr or "")
                        if " > " in repr_str:
                            parts = repr_str.split(" > ", 1)
                            host_name = host_name or parts[0].strip()
                            interface_name = interface_name or parts[1].strip()
                        elif ": " in repr_str:
                            parts = repr_str.split(": ", 1)
                            host_name = host_name or parts[0].strip()
                            interface_name = interface_name or parts[1].strip()
                        else:
                            interface_name = interface_name or repr_str.strip()

                        if not host_name:
                            inf_payload = inf_change.postchange_data or inf_change.prechange_data or {}
                            if isinstance(inf_payload, dict):
                                vm_val = inf_payload.get("virtual_machine")
                                if isinstance(vm_val, dict):
                                    host_name = host_name or vm_val.get("name") or vm_val.get("display") or ""
                                elif isinstance(vm_val, str) and vm_val:
                                    host_name = host_name or vm_val
                                elif isinstance(vm_val, int) and vm_val:
                                    try:
                                        from virtualization.models import VirtualMachine
                                        vm_obj = VirtualMachine.objects.filter(pk=vm_val).first()
                                        if vm_obj:
                                            host_name = host_name or vm_obj.name
                                    except Exception:
                                        pass
                except Exception:
                    pass

        # If target_model is unknown
        else:
            # If dns_name matches a Device name in NetBox, try Device Interface first
            if dns_name:
                try:
                    from dcim.models import Device
                    if Device.objects.filter(name__iexact=dns_name).exists():
                        target_model = "interface"
                except Exception:
                    pass

            if target_model != "vminterface":
                try:
                    from dcim.models import Interface
                    inf = Interface.objects.filter(pk=assigned_id).select_related("device").first()
                    if inf:
                        host_name = host_name or getattr(inf.device, "name", "")
                        interface_name = interface_name or inf.name
                except Exception:
                    pass

            if not host_name:
                try:
                    from virtualization.models import VMInterface
                    vminf = VMInterface.objects.filter(pk=assigned_id).select_related("virtual_machine").first()
                    if vminf:
                        host_name = host_name or getattr(vminf.virtual_machine, "name", "")
                        interface_name = interface_name or vminf.name
                except Exception:
                    pass

            if not host_name or not interface_name:
                try:
                    from core.models import ObjectChange
                    inf_change = ObjectChange.objects.filter(
                        changed_object_id=assigned_id,
                        changed_object_type__model="interface"
                    ).order_by("-time").first()
                    if inf_change:
                        repr_str = str(inf_change.object_repr or "")
                        if " > " in repr_str:
                            parts = repr_str.split(" > ", 1)
                            host_name = host_name or parts[0].strip()
                            interface_name = interface_name or parts[1].strip()
                        elif ": " in repr_str:
                            parts = repr_str.split(": ", 1)
                            host_name = host_name or parts[0].strip()
                            interface_name = interface_name or parts[1].strip()
                        else:
                            interface_name = interface_name or repr_str.strip()
                except Exception:
                    pass

    # 4. Consistency check between dns_name and host_name
    if dns_name and host_name and host_name != dns_name:
        try:
            from dcim.models import Device
            from virtualization.models import VirtualMachine
            if Device.objects.filter(name__iexact=dns_name).exists():
                # dns_name is a known physical Device; if host_name is a VM or different, prioritize Device
                if VirtualMachine.objects.filter(name__iexact=host_name).exists() or not Device.objects.filter(name__iexact=host_name).exists():
                    host_name = dns_name
            elif VirtualMachine.objects.filter(name__iexact=dns_name).exists():
                # dns_name is a known VirtualMachine; prioritize VM
                if Device.objects.filter(name__iexact=host_name).exists() or not VirtualMachine.objects.filter(name__iexact=host_name).exists():
                    host_name = dns_name
        except Exception:
            pass

    # 5. Fallback from dns_name if host_name is still empty
    if not host_name and dns_name:
        try:
            from dcim.models import Device
            dev = Device.objects.filter(name__iexact=dns_name).first()
            if dev:
                host_name = dev.name
        except Exception:
            pass

        if not host_name:
            try:
                from virtualization.models import VirtualMachine
                vm = VirtualMachine.objects.filter(name__iexact=dns_name).first()
                if vm:
                    host_name = vm.name
            except Exception:
                pass

    # 6. VRF resolution
    vrf = payload.get("vrf")
    vrf_name = "Global"
    if isinstance(vrf, dict):
        vrf_name = vrf.get("name") or vrf.get("rd") or vrf.get("display") or "Global"
    elif isinstance(vrf, str) and vrf:
        vrf_name = vrf
    elif isinstance(vrf, int):
        try:
            from ipam.models import VRF
            vrf_obj = VRF.objects.filter(pk=vrf).first()
            if vrf_obj:
                vrf_name = vrf_obj.name
        except Exception:
            pass

    # 7. Status
    status = payload.get("status")
    status_str = ""
    if isinstance(status, dict):
        status_str = status.get("label") or status.get("value") or ""
    elif isinstance(status, str):
        status_str = status

    return {
        "host_name": host_name,
        "interface_name": interface_name,
        "dns_name": dns_name,
        "description": description,
        "vrf_name": vrf_name,
        "status": status_str,
    }


_OWNER_TYPE_BY_ASSIGNED_TYPE = {
    "interface": "device",
    "vminterface": "virtualmachine",
    "fhrpgroup": "fhrpgroup",
}


def _guess_owner_type(payload, change=None):
    """
    Best-effort guess of whether an assigned owner is a Device or a
    VirtualMachine, for an ObjectChange payload. Delegates to
    resolve_assigned_object_type(), which already handles every shape these
    payloads actually take — including real native ObjectChange records,
    whose assigned_object_type is a raw ContentType integer PK with no
    nested "assigned_object" dict at all (that shape only appears in
    REST-API-style test fixtures, not in Django's serialize_object() output
    that core.ObjectChange actually stores). Returns 'device',
    'virtualmachine', 'fhrpgroup', or '' if undetermined. Used only to
    distinguish REASSIGNED (same owner type) from OWNER_CHANGED (owner type
    itself changed); callers should treat '' as "unknown" and default to
    the more conservative REASSIGNED rather than assuming a type change.
    """
    if not isinstance(payload, dict):
        return ""
    target = resolve_assigned_object_type(payload, change)
    return _OWNER_TYPE_BY_ASSIGNED_TYPE.get(target, "")


def classify_event_type(action, user_str="", pre_payload=None, post_payload=None,
                         pre_details=None, post_details=None, pre_status=None, post_status=None):
    """
    Determine the most specific EventType for a NetBox ObjectChange action.

    create/delete are classified as before (DISCOVERED when the acting user
    looks like a ping/discovery/scan job, else CREATED; DELETED). For
    'update' actions, pre/post details (as returned by
    extract_netbox_change_details for the prechange/postchange payloads) are
    diffed to distinguish a real lifecycle transition from a generic update:

      - STATUS_CHANGED takes priority over everything else (existing rule).
      - ASSIGNED / UNASSIGNED: the resolved owner (host_name) appeared or
        disappeared entirely.
      - REASSIGNED / OWNER_CHANGED: the owner changed to a different
        device/VM; OWNER_CHANGED specifically when the owner's *type* also
        changed (device <-> virtual machine), REASSIGNED otherwise.
      - INTERFACE_CHANGED: same owner, different interface.
      - DNS_CHANGED / HOSTNAME_CHANGED: the IP's own dns_name / hostname
        field changed with no assignment change.
      - UPDATED: fallback when nothing more specific applies.

    Returns None for any action other than create/delete/update, so callers
    can apply their own existing fallback for unrecognized action values.
    """
    action = str(action or "").lower()
    user_str = str(user_str or "").lower()

    if action == "create":
        if any(hint in user_str for hint in ("ping", "discover", "scan")):
            return EventType.DISCOVERED
        return EventType.CREATED

    if action == "delete":
        return EventType.DELETED

    if action != "update":
        return None

    if pre_status and post_status and str(pre_status).lower() != str(post_status).lower():
        return EventType.STATUS_CHANGED

    pre_details = pre_details or {}
    post_details = post_details or {}

    pre_host = str(pre_details.get("host_name") or "").strip()
    post_host = str(post_details.get("host_name") or "").strip()

    if pre_host.lower() != post_host.lower():
        if not pre_host:
            return EventType.ASSIGNED
        if not post_host:
            return EventType.UNASSIGNED
        pre_owner_type = _guess_owner_type(pre_payload)
        post_owner_type = _guess_owner_type(post_payload)
        if pre_owner_type and post_owner_type and pre_owner_type != post_owner_type:
            return EventType.OWNER_CHANGED
        return EventType.REASSIGNED

    pre_iface = str(pre_details.get("interface_name") or "").strip()
    post_iface = str(post_details.get("interface_name") or "").strip()
    if pre_host and pre_iface.lower() != post_iface.lower() and (pre_iface or post_iface):
        return EventType.INTERFACE_CHANGED

    pre_dns = str(pre_details.get("dns_name") or "").strip()
    post_dns = str(post_details.get("dns_name") or "").strip()
    if pre_dns.lower() != post_dns.lower() and (pre_dns or post_dns):
        return EventType.DNS_CHANGED

    pre_hostname_raw = str((pre_payload or {}).get("hostname") or "").strip()
    post_hostname_raw = str((post_payload or {}).get("hostname") or "").strip()
    if pre_hostname_raw.lower() != post_hostname_raw.lower() and (pre_hostname_raw or post_hostname_raw):
        return EventType.HOSTNAME_CHANGED

    return EventType.UPDATED


_NEW_EVENT_TYPE_LABELS = {
    EventType.ASSIGNED: "Assigned",
    EventType.UNASSIGNED: "Unassigned",
    EventType.REASSIGNED: "Reassigned",
    EventType.OWNER_CHANGED: "Owner changed",
    EventType.INTERFACE_CHANGED: "Interface changed",
    EventType.DNS_CHANGED: "DNS changed",
    EventType.HOSTNAME_CHANGED: "Hostname changed",
}


def format_native_event_display(event_type, curr_status="", post_status=""):
    """
    Human-readable label for a classified native event. Preserves the exact
    existing conventions for the original event types (status suffix on
    Created/Discovered, 'Status: X' on status changes) and adds plain labels
    for the newer lifecycle-transition types.
    """
    if event_type == EventType.DISCOVERED:
        return "Discovered" if not curr_status else f"Discovered ({str(curr_status).title()})"
    if event_type == EventType.CREATED:
        return "Created" if not curr_status else f"Created ({str(curr_status).title()})"
    if event_type == EventType.DELETED:
        return "Deleted"
    if event_type == EventType.STATUS_CHANGED:
        return f"Status: {str(post_status).title()}" if post_status else "Status changed"
    if event_type == EventType.UPDATED:
        return "Updated"
    if event_type in _NEW_EVENT_TYPE_LABELS:
        return _NEW_EVENT_TYPE_LABELS[event_type]
    return str(event_type).replace("_", " ").title()


def native_events(ip_address, date_from=None, date_to=None, username=None, exclude_pks=None):
    """Read ObjectChange snapshots by canonical IP, retaining deleted names and status changes."""
    try:
        from core.models import ObjectChange
    except ImportError:
        return []

    from .normalize import normalize_ip

    try:
        canonical_ip, _ = normalize_ip(str(ip_address))
    except Exception:
        canonical_ip = str(ip_address).split("/")[0].strip()

    events = []
    # Narrow at the database level before the exact-match Python filter
    # below: without this, every ipaddress ObjectChange row in the entire
    # NetBox installation is loaded into Python and inspected on every
    # timeline view, regardless of which IP was requested — a full-table
    # scan on every page load. This OR's together every field
    # extract_ip_from_change() itself checks (postchange/prechange "address"
    # first, object_repr as its own fallback), in the same priority order,
    # so it can't introduce a false negative the Python-side logic wouldn't
    # also have missed: it's the same trusted source, just evaluated in SQL
    # first. "startswith" on "<ip>/" (never a bare substring match) pins
    # the boundary so an unrelated address sharing a prefix is excluded,
    # e.g. "172.17.8.8" must not match "172.17.8.80". The exact Python-side
    # comparison further down still runs on the (now much smaller)
    # candidate set as the final correctness authority — this is purely a
    # narrowing pre-filter, never the source of truth.
    ip_filter = Q()
    for field in ("postchange_data__address", "prechange_data__address", "object_repr"):
        ip_filter |= Q(**{field: canonical_ip}) | Q(**{f"{field}__startswith": f"{canonical_ip}/"})
    queryset = ObjectChange.objects.filter(changed_object_type__model="ipaddress").filter(ip_filter).order_by("-time")
    if date_from:
        queryset = queryset.filter(time__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(time__date__lte=date_to)
    if username:
        queryset = queryset.filter(user_name__icontains=username)

    exclude_set = set(str(pk) for pk in (exclude_pks or []))

    for change in queryset:
        if str(change.pk) in exclude_set:
            continue

        change_ip, prefix_len = extract_ip_from_change(change)
        if not change_ip or change_ip != canonical_ip:
            continue

        payloads = [change.postchange_data or {}, change.prechange_data or {}]
        payload = next((item for item in payloads if item), {})
        details = extract_netbox_change_details(payload, change)

        action = str(change.action).lower()
        pre = getattr(change, "prechange_data", {}) or {}
        post = getattr(change, "postchange_data", {}) or {}
        pre_status = pre.get("status")
        post_status = post.get("status")
        if isinstance(pre_status, dict):
            pre_status = pre_status.get("label") or pre_status.get("value")
        if isinstance(post_status, dict):
            post_status = post_status.get("label") or post_status.get("value")

        user_str = str(change.user_name or "").lower()
        curr_status = details.get("status") or post_status or pre_status or ""

        pre_details = extract_netbox_change_details(pre, change) if action == "update" and pre else {}
        post_details = extract_netbox_change_details(post, change) if action == "update" and post else {}

        event_type = classify_event_type(
            action, user_str,
            pre_payload=pre, post_payload=post,
            pre_details=pre_details, post_details=post_details,
            pre_status=pre_status, post_status=post_status,
        ) or action
        event_type_display = format_native_event_display(event_type, curr_status, post_status)

        events.append({
            "pk": change.pk,
            "timestamp": change.time,
            "event_type": event_type,
            "event_type_display": event_type_display,
            "source": "NetBox",
            "ip_address": canonical_ip,
            "hostname": details["dns_name"] or details["host_name"],
            "description": details["description"],
            "username": change.user_name or "",
            "native": True,
            "raw_reference": change.pk,
            "owner_name": details["host_name"],
            "interface_name": details["interface_name"],
            "dns_name": details["dns_name"],
            "vrf": details["vrf_name"] or "Global",
        })
    return events


def get_timeline(ip_address, vrf="", source="", event_type="", oldest_first=False, date_from=None, date_to=None, owner="", username=""):
    canonical_ip = str(ip_address).split("/")[0].strip()
    scope = Q()
    if vrf == "Global":
        scope = Q(vrf_name="") & Q(vrf_rd="")
    elif vrf:
        scope = Q(vrf_name__icontains=vrf) | Q(vrf_rd__icontains=vrf)
    query = HistoricalIPEvent.objects.filter(ip_address=canonical_ip).filter(scope).select_related("source", "import_job")
    if source:
        query = query.filter(Q(source__slug__icontains=source) | Q(source__name__icontains=source))
    if event_type:
        query = query.filter(event_type=event_type)
    if date_from:
        query = query.filter(timestamp__date__gte=date_from)
    if date_to:
        query = query.filter(timestamp__date__lte=date_to)
    if owner:
        query = query.filter(
            Q(owner_name__icontains=owner)
            | Q(hostname__icontains=owner)
            | Q(device_name__icontains=owner)
            | Q(virtual_machine_name__icontains=owner)
        )
    if username:
        query = query.filter(source_username__icontains=username)

    events = []
    for item in query:
        owner_name = item.owner_name or item.device_name or item.virtual_machine_name or item.hostname
        interface_name = item.interface_name
        hostname = item.hostname
        dns_name = item.dns_name

        # If native NetBox event, re-extract or validate against raw_data / dns_name
        if getattr(item.source, "slug", "") == "netbox":
            raw = item.raw_data or {}
            payloads = [raw.get("postchange_data") or {}, raw.get("prechange_data") or {}]
            payload = next((p for p in payloads if isinstance(p, dict) and p), {})
            if payload:
                re_details = extract_netbox_change_details(payload)
                if re_details.get("host_name"):
                    owner_name = re_details["host_name"]
                if re_details.get("interface_name"):
                    interface_name = re_details["interface_name"]
                if re_details.get("dns_name"):
                    dns_name = re_details["dns_name"]
                if re_details.get("dns_name") or re_details.get("host_name"):
                    hostname = re_details["dns_name"] or re_details["host_name"]
            elif dns_name and owner_name and owner_name != dns_name:
                try:
                    from dcim.models import Device
                    if Device.objects.filter(name__iexact=dns_name).exists():
                        owner_name = dns_name
                except Exception:
                    pass

        events.append({
            "pk": item.pk,
            "timestamp": item.timestamp,
            "event_type": item.event_type,
            "event_type_display": item.get_event_type_display() if hasattr(item, "get_event_type_display") else str(item.event_type).title(),
            "source": item.source.name,
            "ip_address": item.ip_address,
            "vrf": item.vrf_name or item.vrf_rd or "Global / Unknown",
            "owner_type": item.owner_type,
            "owner_name": owner_name,
            "interface_name": interface_name,
            "hostname": hostname,
            "dns_name": dns_name,
            "description": item.description,
            "username": item.source_username,
            "native": (item.source.slug == "netbox"),
            "raw_reference": item,
        })

    if not source or "netbox" in source.lower():
        synced_netbox_pks = {
            item.source_record_id for item in query if getattr(item.source, "slug", "") == "netbox" and item.source_record_id
        }
        events.extend(
            native_events(
                canonical_ip,
                date_from=date_from,
                date_to=date_to,
                username=username,
                exclude_pks=synced_netbox_pks,
            )
        )
    return sorted(events, key=lambda item: item["timestamp"], reverse=not oldest_first)


class NativeEventWrapper:
    """Wraps core.models.ObjectChange into a HistoricalIPEvent-compatible interface for detail rendering."""
    def __init__(self, change, ip_address=None):
        import json
        self.pk = change.pk
        self.timestamp = change.time
        self.source_record_id = f"ObjectChange #{change.pk}"
        self.source_username = getattr(change, "user_name", "") or ""
        self.import_job = None

        class DummySource:
            name = "NetBox"
            slug = "netbox"

        self.source = DummySource()

        payloads = [getattr(change, "postchange_data", {}) or {}, getattr(change, "prechange_data", {}) or {}]
        payload = next((p for p in payloads if p), {})
        details = extract_netbox_change_details(payload, change)

        change_ip, prefix_len = extract_ip_from_change(change)
        self.ip_address = change_ip or str(ip_address or "").split("/")[0].strip()
        self.prefix_length = prefix_len

        self.vrf_name = details.get("vrf_name") or "Global"
        self.vrf_rd = None
        self.dns_name = details.get("dns_name")
        self.hostname = details.get("dns_name") or details.get("host_name")
        self.owner_name = details.get("host_name")
        self.device_name = details.get("host_name")
        self.virtual_machine_name = None
        self.interface_name = details.get("interface_name")
        self.mac_address = None
        self.description = details.get("description")

        action = str(getattr(change, "action", "")).lower()
        pre = getattr(change, "prechange_data", {}) or {}
        post = getattr(change, "postchange_data", {}) or {}
        pre_status = pre.get("status")
        post_status = post.get("status")
        if isinstance(pre_status, dict):
            pre_status = pre_status.get("label") or pre_status.get("value")
        if isinstance(post_status, dict):
            post_status = post_status.get("label") or post_status.get("value")

        user_str = str(getattr(change, "user_name", "") or "").lower()

        pre_details = extract_netbox_change_details(pre, change) if action == "update" and pre else {}
        post_details = extract_netbox_change_details(post, change) if action == "update" and post else {}

        self.event_type = classify_event_type(
            action, user_str,
            pre_payload=pre, post_payload=post,
            pre_details=pre_details, post_details=post_details,
            pre_status=pre_status, post_status=post_status,
        ) or action

        snapshot = {
            "objectchange_id": change.pk,
            "action": getattr(change, "action", ""),
            "user": getattr(change, "user_name", ""),
            "timestamp": str(getattr(change, "time", "")),
            "changed_object_type": str(getattr(change, "changed_object_type", "")),
            "postchange_data": getattr(change, "postchange_data", {}),
            "prechange_data": getattr(change, "prechange_data", {}),
        }
        self.raw_data = json.dumps(snapshot, indent=2, default=str)

    def get_event_type_display(self):
        action_map = {
            "created": "Created",
            "create": "Created",
            "updated": "Updated",
            "update": "Updated",
            "deleted": "Deleted",
            "delete": "Deleted",
            "discovered": "Discovered",
            "status_changed": "Status Changed",
            "assigned": "Assigned",
            "unassigned": "Unassigned",
            "reassigned": "Reassigned",
            "owner_changed": "Owner Changed",
            "interface_changed": "Interface Changed",
            "dns_changed": "DNS Changed",
            "hostname_changed": "Hostname Changed",
        }
        return action_map.get(self.event_type, self.event_type.title())