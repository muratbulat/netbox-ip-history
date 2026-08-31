from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("efficientip")
class EfficientIPImporter(RegisteredVendorImporter):
    display_name = "EfficientIP SOLIDserver"
    support_level = SupportLevel.EXPERIMENTAL
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.INVENTORY_API, ImportCapability.ADDRESSES, ImportCapability.PREFIXES, ImportCapability.DNS, ImportCapability.HISTORY_FILE}