from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("micetro")
class MicetroImporter(RegisteredVendorImporter):
    display_name = "BlueCat Micetro / Men&Mice"
    support_level = SupportLevel.EXPERIMENTAL
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.INVENTORY_API, ImportCapability.ADDRESSES, ImportCapability.PREFIXES, ImportCapability.DNS, ImportCapability.HISTORY_FILE}