from .base import BaseImporter, Capability, SupportLevel
from .generic_csv import GenericCSVImporter, GenericJSONImporter
from .gestioip import GestioIPImporter
from .infoblox import InfobloxImporter
from .netbox_export import NetBoxExportImporter
from .phpipam import PhpIPAMImporter
from .vendor_file import VENDOR_PROFILES, VendorFileImporter, vendor_importer

__all__ = (
    "IMPORTERS",
    "BaseImporter",
    "Capability",
    "SupportLevel",
    "importer_for",
    "support_matrix",
)

#: source_type -> importer class. The native "netbox" source is fed by signals, not files.
IMPORTERS: dict[str, type[BaseImporter]] = {
    cls.source_type: cls
    for cls in (
        GenericCSVImporter,
        GenericJSONImporter,
        GestioIPImporter,
        InfobloxImporter,
        NetBoxExportImporter,
        PhpIPAMImporter,
    )
}
IMPORTERS.update({source_type: vendor_importer(source_type) for source_type in VENDOR_PROFILES})


def importer_for(source_type: str) -> type[BaseImporter]:
    """Importer for a source type; unknown types fall back to generic content sniffing."""
    return IMPORTERS.get(source_type, VendorFileImporter)


def support_matrix() -> list[dict]:
    return [
        {
            "source_type": source_type,
            "name": cls.display_name,
            "support_level": cls.support_level.value,
            "formats": list(cls.formats),
            "capabilities": sorted(c.value for c in cls.capabilities),
        }
        for source_type, cls in sorted(IMPORTERS.items(), key=lambda item: item[1].display_name.lower())
    ]
