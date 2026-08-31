from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("device42")
class Device42Importer(RegisteredVendorImporter):
    display_name = "Device42"
    support_level = SupportLevel.EXPERIMENTAL
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.INVENTORY_API, ImportCapability.ADDRESSES, ImportCapability.PREFIXES, ImportCapability.VRFS, ImportCapability.DEVICES, ImportCapability.INTERFACES, ImportCapability.DNS}