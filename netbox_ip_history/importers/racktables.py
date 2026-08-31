from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("racktables")
class RackTablesImporter(RegisteredVendorImporter):
    display_name = "RackTables"
    support_level = SupportLevel.EXPORT
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.READONLY_DATABASE, ImportCapability.ADDRESSES, ImportCapability.PREFIXES, ImportCapability.DEVICES, ImportCapability.INTERFACES, ImportCapability.VLANS}