from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("nautobot")
class NautobotImporter(RegisteredVendorImporter):
    display_name = "Nautobot"
    support_level = SupportLevel.EXPERIMENTAL
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.INVENTORY_API, ImportCapability.ADDRESSES, ImportCapability.PREFIXES, ImportCapability.VRFS, ImportCapability.DEVICES, ImportCapability.INTERFACES}