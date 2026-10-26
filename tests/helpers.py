import uuid
from datetime import UTC, datetime, timedelta

from core.models import ObjectChange
from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
from django.contrib.contenttypes.models import ContentType
from ipam.models import IPAddress
from virtualization.models import VirtualMachine, VMInterface

from netbox_ip_history.models import ImportSource
from netbox_ip_history.signals import record_object_changes

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_device(name):
    site, _ = Site.objects.get_or_create(name="Site 1", slug="site-1")
    manufacturer, _ = Manufacturer.objects.get_or_create(name="Manufacturer 1", slug="manufacturer-1")
    device_type, _ = DeviceType.objects.get_or_create(manufacturer=manufacturer, model="Model 1", slug="model-1")
    role, _ = DeviceRole.objects.get_or_create(name="Role 1", slug="role-1")
    return Device.objects.create(name=name, site=site, device_type=device_type, role=role)


def make_interface(device, name="eth0"):
    return Interface.objects.create(device=device, name=name, type="1000base-t")


def make_vm_interface(vm_name, name="eth0"):
    vm = VirtualMachine.objects.create(name=vm_name)
    return VMInterface.objects.create(virtual_machine=vm, name=name)


def ip_change(address, action="create", pre=None, post=None, minutes=0, user_name="admin", object_id=1):
    """Create an ipaddress ObjectChange (the plugin's post_save receiver records it)."""
    change = ObjectChange.objects.create(
        changed_object_type=ContentType.objects.get_for_model(IPAddress),
        changed_object_id=object_id,
        action=action,
        object_repr=address,
        prechange_data=pre,
        postchange_data=post if post is not None else ({"address": address} if action != "delete" else None),
        user_name=user_name,
        request_id=uuid.uuid4(),
    )
    ObjectChange.objects.filter(pk=change.pk).update(time=BASE_TIME + timedelta(minutes=minutes))
    change.refresh_from_db()
    record_object_changes([change])  # re-record with the backdated time
    return change


def make_source(slug="lab-csv", source_type="generic_csv", **kwargs):
    return ImportSource.objects.create(name=slug, slug=slug, source_type=source_type, **kwargs)
