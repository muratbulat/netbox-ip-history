from .generic_csv import GenericCSVImporter
from .generic_json import GenericJSONImporter
from .gestioip import GestioIPImporter
from .phpipam import PhpIPAMImporter
from .generic_sql import GenericSQLImporter
from .registry import IMPORTERS, importer_for, register_importer, support_matrix
from .racktables import RackTablesImporter
from .glpi import GLPIImporter
from .device42 import Device42Importer
from .infoblox import InfobloxImporter
from .bluecat import BlueCatImporter
from .micetro import MicetroImporter
from .efficientip import EfficientIPImporter
from .nipap import NIPAPImporter
from .teemip import TeemIPImporter
from .solarwinds import SolarWindsImporter
from .manageengine import ManageEngineImporter
from .microsoft_ipam import MicrosoftIPAMImporter
from .netbox import NetBoxImporter
from .nautobot import NautobotImporter
from .ralph import RalphImporter
from .netbox_ping import NetBoxPingImporter

__all__ = (
    "GenericCSVImporter", "GenericJSONImporter", "GestioIPImporter", "PhpIPAMImporter",
    "GenericSQLImporter", "RackTablesImporter", "GLPIImporter", "Device42Importer",
    "InfobloxImporter", "BlueCatImporter", "MicetroImporter", "EfficientIPImporter",
    "NIPAPImporter", "TeemIPImporter", "SolarWindsImporter", "ManageEngineImporter",
    "MicrosoftIPAMImporter", "NetBoxImporter", "NautobotImporter", "RalphImporter",
    "NetBoxPingImporter",
    "IMPORTERS", "importer_for", "register_importer", "support_matrix",
)

register_importer("gestioip")(GestioIPImporter)
register_importer("phpipam")(PhpIPAMImporter)
register_importer("generic_csv")(GenericCSVImporter)
register_importer("generic_json")(GenericJSONImporter)
register_importer("generic_sql")(GenericSQLImporter)
register_importer("other")(GenericCSVImporter)
register_importer("racktables")(RackTablesImporter)
register_importer("glpi")(GLPIImporter)
register_importer("device42")(Device42Importer)
register_importer("infoblox")(InfobloxImporter)
register_importer("bluecat")(BlueCatImporter)
register_importer("micetro")(MicetroImporter)
register_importer("efficientip")(EfficientIPImporter)
register_importer("nipap")(NIPAPImporter)
register_importer("teemip")(TeemIPImporter)
register_importer("solarwinds")(SolarWindsImporter)
register_importer("manageengine")(ManageEngineImporter)
register_importer("microsoft_ipam")(MicrosoftIPAMImporter)
register_importer("netbox")(NetBoxImporter)
register_importer("nautobot")(NautobotImporter)
register_importer("ralph")(RalphImporter)
register_importer("netbox_ping")(NetBoxPingImporter)
