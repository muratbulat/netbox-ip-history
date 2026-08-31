from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("microsoft_ipam")
class MicrosoftIPAMImporter(RegisteredVendorImporter):
    display_name = "Microsoft Windows Server IPAM"
    support_level = SupportLevel.EXPORT
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.ADDRESSES, ImportCapability.PREFIXES, ImportCapability.DNS}