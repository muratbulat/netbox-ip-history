from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("teemip")
class TeemIPImporter(RegisteredVendorImporter):
    display_name = "TeemIP / iTop"
    support_level = SupportLevel.EXPORT
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.INVENTORY_API, ImportCapability.ADDRESSES, ImportCapability.PREFIXES, ImportCapability.VRFS, ImportCapability.VLANS, ImportCapability.DNS, ImportCapability.HISTORY_FILE}