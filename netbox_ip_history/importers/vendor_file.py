"""
Data-driven importer for sources without a dedicated parser.

Every profile below parses the uploaded export generically (CSV, JSON or flat XML,
detected from content) using the shared column aliases. Profiles only describe the
source; they do not imply vendor-specific parsing. Sources with real format-specific
logic live in their own modules (gestioip, phpipam, infoblox, netbox_export).
"""

from .base import BaseImporter, Capability
from .generic_csv import iter_json_rows, iter_xml_rows

__all__ = ("VENDOR_PROFILES", "VendorFileImporter", "vendor_importer")

C = Capability

#: source_type -> (display name, declared capabilities of the source's exports)
VENDOR_PROFILES: dict[str, tuple[str, frozenset[Capability]]] = {
    "bluecat": ("BlueCat Address Manager", frozenset({C.ADDRESSES, C.PREFIXES, C.DNS})),
    "device42": ("Device42", frozenset({C.ADDRESSES, C.PREFIXES, C.VRFS, C.DEVICES, C.INTERFACES, C.DNS})),
    "efficientip": ("EfficientIP SOLIDserver", frozenset({C.ADDRESSES, C.PREFIXES, C.DNS, C.HISTORY})),
    "glpi": ("GLPI", frozenset({C.ADDRESSES, C.DEVICES, C.INTERFACES})),
    "manageengine": ("ManageEngine OpUtils", frozenset({C.ADDRESSES, C.PREFIXES})),
    "micetro": ("BlueCat Micetro", frozenset({C.ADDRESSES, C.PREFIXES, C.DNS, C.HISTORY})),
    "microsoft_ipam": ("Microsoft Windows Server IPAM", frozenset({C.ADDRESSES, C.PREFIXES, C.DNS})),
    "nautobot": ("Nautobot", frozenset({C.ADDRESSES, C.PREFIXES, C.VRFS, C.DEVICES, C.INTERFACES})),
    "nipap": ("NIPAP", frozenset({C.ADDRESSES, C.PREFIXES, C.VRFS})),
    "racktables": ("RackTables", frozenset({C.ADDRESSES, C.PREFIXES, C.DEVICES, C.INTERFACES})),
    "ralph": ("Ralph", frozenset({C.ADDRESSES, C.DEVICES, C.INTERFACES})),
    "solarwinds": ("SolarWinds IPAM", frozenset({C.ADDRESSES, C.PREFIXES, C.DNS})),
    "teemip": ("TeemIP / iTop", frozenset({C.ADDRESSES, C.PREFIXES, C.VRFS, C.DNS, C.HISTORY})),
    "other": ("Other / generic export", frozenset({C.ADDRESSES, C.HISTORY})),
}


class VendorFileImporter(BaseImporter):
    display_name = "Generic export"
    formats = ("csv", "json", "xml")

    def iter_records(self):
        text = self.read_text()
        head = text.lstrip()[:1]
        if head in ("[", "{"):
            rows = iter_json_rows(text)
        elif head == "<":
            rows = iter_xml_rows(text)
        else:
            rows = self.iter_csv_rows(text)
        for row in rows:
            yield self.to_record(row)


def vendor_importer(source_type: str) -> type[VendorFileImporter]:
    display_name, capabilities = VENDOR_PROFILES[source_type]
    return type(
        f"{source_type.title().replace('_', '')}Importer",
        (VendorFileImporter,),
        {"source_type": source_type, "display_name": display_name, "capabilities": capabilities},
    )
