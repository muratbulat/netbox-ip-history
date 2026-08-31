from enum import Enum


class ImportCapability(str, Enum):
    INVENTORY_API = "inventory_api"
    HISTORY_API = "history_api"
    INVENTORY_FILE = "inventory_file"
    HISTORY_FILE = "history_file"
    READONLY_DATABASE = "readonly_database"
    BACKUP_IMPORT = "backup_import"
    PREFIXES = "prefixes"
    ADDRESSES = "addresses"
    VLANS = "vlans"
    VRFS = "vrfs"
    DNS = "dns"
    DEVICES = "devices"
    INTERFACES = "interfaces"
    HISTORY = "history"


class SupportLevel(str, Enum):
    FULL = "full"
    INVENTORY = "inventory"
    HISTORY = "history"
    EXPORT = "export"
    EXPERIMENTAL = "experimental"