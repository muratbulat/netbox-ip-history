from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("netbox")
class NetBoxImporter(RegisteredVendorImporter):
    display_name = "Another NetBox instance"
    support_level = SupportLevel.EXPERIMENTAL
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.INVENTORY_API, ImportCapability.ADDRESSES, ImportCapability.PREFIXES, ImportCapability.VRFS, ImportCapability.VLANS, ImportCapability.DEVICES, ImportCapability.INTERFACES, ImportCapability.HISTORY_API, ImportCapability.HISTORY}