from django.utils.translation import gettext_lazy as _
from utilities.choices import ChoiceSet


class EventTypeChoices(ChoiceSet):
    CREATED = "created"
    DELETED = "deleted"
    UPDATED = "updated"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    REASSIGNED = "reassigned"
    HOSTNAME_CHANGED = "hostname_changed"
    DNS_CHANGED = "dns_changed"
    STATUS_CHANGED = "status_changed"
    DESCRIPTION_CHANGED = "description_changed"
    OWNER_CHANGED = "owner_changed"
    INTERFACE_CHANGED = "interface_changed"
    IMPORTED = "imported"
    DISCOVERED = "discovered"
    UNKNOWN = "unknown"

    CHOICES = [
        (CREATED, _("Created"), "green"),
        (DELETED, _("Deleted"), "red"),
        (UPDATED, _("Updated"), "blue"),
        (ASSIGNED, _("Assigned"), "green"),
        (UNASSIGNED, _("Unassigned"), "red"),
        (REASSIGNED, _("Reassigned"), "cyan"),
        (HOSTNAME_CHANGED, _("Hostname changed"), "azure"),
        (DNS_CHANGED, _("DNS changed"), "azure"),
        (STATUS_CHANGED, _("Status changed"), "yellow"),
        (DESCRIPTION_CHANGED, _("Description changed"), "purple"),
        (OWNER_CHANGED, _("Owner changed"), "purple"),
        (INTERFACE_CHANGED, _("Interface changed"), "purple"),
        (IMPORTED, _("Imported"), "teal"),
        (DISCOVERED, _("Discovered"), "indigo"),
        (UNKNOWN, _("Unknown"), "gray"),
    ]


class SourceTypeChoices(ChoiceSet):
    NETBOX = "netbox"
    GENERIC_CSV = "generic_csv"
    GENERIC_JSON = "generic_json"
    GESTIOIP = "gestioip"
    PHPIPAM = "phpipam"
    INFOBLOX = "infoblox"
    NETBOX_EXPORT = "netbox_export"
    BLUECAT = "bluecat"
    DEVICE42 = "device42"
    EFFICIENTIP = "efficientip"
    GLPI = "glpi"
    MANAGEENGINE = "manageengine"
    MICETRO = "micetro"
    MICROSOFT_IPAM = "microsoft_ipam"
    NAUTOBOT = "nautobot"
    NIPAP = "nipap"
    RACKTABLES = "racktables"
    RALPH = "ralph"
    SOLARWINDS = "solarwinds"
    TEEMIP = "teemip"
    OTHER = "other"

    CHOICES = [
        (NETBOX, "NetBox (native)"),
        (GENERIC_CSV, "CSV"),
        (GENERIC_JSON, "JSON"),
        (GESTIOIP, "GestióIP"),
        (PHPIPAM, "phpIPAM"),
        (INFOBLOX, "Infoblox NIOS"),
        (NETBOX_EXPORT, "NetBox changelog export"),
        (BLUECAT, "BlueCat Address Manager"),
        (DEVICE42, "Device42"),
        (EFFICIENTIP, "EfficientIP SOLIDserver"),
        (GLPI, "GLPI"),
        (MANAGEENGINE, "ManageEngine OpUtils"),
        (MICETRO, "BlueCat Micetro"),
        (MICROSOFT_IPAM, "Microsoft Windows Server IPAM"),
        (NAUTOBOT, "Nautobot"),
        (NIPAP, "NIPAP"),
        (RACKTABLES, "RackTables"),
        (RALPH, "Ralph"),
        (SOLARWINDS, "SolarWinds IPAM"),
        (TEEMIP, "TeemIP / iTop"),
        (OTHER, _("Other")),
    ]


class DateOrderChoices(ChoiceSet):
    DAY_FIRST = "dmy"
    MONTH_FIRST = "mdy"

    CHOICES = [
        (DAY_FIRST, _("Day first (31/12/2025)")),
        (MONTH_FIRST, _("Month first (12/31/2025)")),
    ]


class ImportModeChoices(ChoiceSet):
    HISTORY_ONLY = "history_only"
    INVENTORY_HISTORY = "inventory_history"

    CHOICES = [
        (HISTORY_ONLY, _("History only")),
        (INVENTORY_HISTORY, _("Inventory and history")),
    ]


class ImportStatusChoices(ChoiceSet):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

    CHOICES = [
        (PENDING, _("Pending"), "cyan"),
        (RUNNING, _("Running"), "blue"),
        (COMPLETED, _("Completed"), "green"),
        (FAILED, _("Failed"), "red"),
        (ROLLED_BACK, _("Rolled back"), "gray"),
    ]
