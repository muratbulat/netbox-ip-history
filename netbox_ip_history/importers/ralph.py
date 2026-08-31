from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("ralph")
class RalphImporter(RegisteredVendorImporter):
    display_name = "Ralph"
    support_level = SupportLevel.EXPORT
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.INVENTORY_API, ImportCapability.ADDRESSES, ImportCapability.DEVICES, ImportCapability.INTERFACES}