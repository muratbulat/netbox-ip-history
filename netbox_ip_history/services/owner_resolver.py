from typing import Any


def resolve_owner(*, device_name: str = "", virtual_machine_name: str = "", hostname: str = "", mac_address: str = "") -> Any | None:
    """Return only unique exact matches; unresolved identity remains metadata."""
    try:
        from dcim.models import Device, Interface
        from virtualization.models import VirtualMachine, VMInterface
    except ImportError:
        return None

    candidates = []
    for model, value in ((Device, device_name or hostname), (VirtualMachine, virtual_machine_name or hostname)):
        if value:
            candidates.extend(model.objects.filter(name=value)[:2])
    if mac_address:
        candidates.extend(Interface.objects.filter(mac_address=mac_address)[:2])
        candidates.extend(VMInterface.objects.filter(mac_address=mac_address)[:2])
    return candidates[0] if len(candidates) == 1 else None