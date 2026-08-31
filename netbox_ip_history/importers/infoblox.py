from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("infoblox")
class InfobloxImporter(RegisteredVendorImporter):
    display_name = "Infoblox NIOS / DDI"
    support_level = SupportLevel.EXPERIMENTAL
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.INVENTORY_API, ImportCapability.ADDRESSES, ImportCapability.PREFIXES, ImportCapability.VRFS, ImportCapability.DNS, ImportCapability.HISTORY_FILE}