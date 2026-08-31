from .capabilities import ImportCapability, SupportLevel
from .importers_vendor_placeholder import RegisteredVendorImporter
from .registry import register_importer


@register_importer("netbox_ping")
class NetBoxPingImporter(RegisteredVendorImporter):
    display_name = "NetBox Ping (ICMP Scanner & Discovery)"
    support_level = SupportLevel.HISTORY
    capabilities = {
        ImportCapability.HISTORY_API,
        ImportCapability.HISTORY,
        ImportCapability.ADDRESSES,
        ImportCapability.VRFS,
    }
