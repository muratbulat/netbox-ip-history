from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("glpi")
class GLPIImporter(RegisteredVendorImporter):
    display_name = "GLPI"
    support_level = SupportLevel.EXPERIMENTAL
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.INVENTORY_API, ImportCapability.ADDRESSES, ImportCapability.DEVICES, ImportCapability.INTERFACES}