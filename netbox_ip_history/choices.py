try:
    from django.db import models
    from django.utils.translation import gettext_lazy as _
    TextChoicesBase = models.TextChoices
except ImportError:
    class TextChoicesMeta(type):
        def __new__(mcls, name, bases, attrs):
            _choices = []
            _values = []
            new_attrs = {}
            for k, v in attrs.items():
                if not k.startswith("_") and isinstance(v, tuple) and len(v) == 2:
                    val, label = v
                    new_attrs[k] = val
                    _choices.append((val, label))
                    _values.append(val)
                else:
                    new_attrs[k] = v
            cls = super().__new__(mcls, name, bases, new_attrs)
            cls._choices = _choices
            cls._values = _values
            return cls

        @property
        def values(cls):
            return getattr(cls, "_values", [])

        @property
        def choices(cls):
            return getattr(cls, "_choices", [])

    class TextChoicesBase(metaclass=TextChoicesMeta):
        pass

    class models:
        TextChoices = TextChoicesBase

    _ = lambda s: s


class EventType(TextChoicesBase):
    CREATED = "created", _("Created")
    DELETED = "deleted", _("Deleted")
    UPDATED = "updated", _("Updated")
    ASSIGNED = "assigned", _("Assigned")
    UNASSIGNED = "unassigned", _("Unassigned")
    REASSIGNED = "reassigned", _("Reassigned")
    HOSTNAME_CHANGED = "hostname_changed", _("Hostname changed")
    DNS_CHANGED = "dns_changed", _("DNS changed")
    STATUS_CHANGED = "status_changed", _("Status changed")
    DESCRIPTION_CHANGED = "description_changed", _("Description changed")
    OWNER_CHANGED = "owner_changed", _("Owner changed")
    INTERFACE_CHANGED = "interface_changed", _("Interface changed")
    IMPORTED = "imported", _("Imported")
    DISCOVERED = "discovered", _("Discovered")
    UNKNOWN = "unknown", _("Unknown")


EVENT_TYPE_COLORS = {
    EventType.CREATED: "success",
    EventType.DELETED: "danger",
    EventType.UPDATED: "primary",
    EventType.ASSIGNED: "success",
    EventType.UNASSIGNED: "danger",
    EventType.REASSIGNED: "cyan",
    EventType.HOSTNAME_CHANGED: "azure",
    EventType.DNS_CHANGED: "azure",
    EventType.STATUS_CHANGED: "yellow",
    EventType.DESCRIPTION_CHANGED: "purple",
    EventType.OWNER_CHANGED: "purple",
    EventType.INTERFACE_CHANGED: "purple",
    EventType.IMPORTED: "teal",
    EventType.DISCOVERED: "indigo",
    EventType.UNKNOWN: "secondary",
}


class SourceType(TextChoicesBase):
    GESTIOIP = "gestioip", "GestióIP"
    PHPIPAM = "phpipam", "phpIPAM"
    GENERIC_CSV = "generic_csv", "CSV"
    GENERIC_JSON = "generic_json", "JSON"
    RACKTABLES = "racktables", "RackTables"
    GLPI = "glpi", "GLPI"
    DEVICE42 = "device42", "Device42"
    INFOBLOX = "infoblox", "Infoblox"
    BLUECAT = "bluecat", "BlueCat"
    MICETRO = "micetro", "Micetro"
    EFFICIENTIP = "efficientip", "EfficientIP"
    NIPAP = "nipap", "NIPAP"
    TEEMIP = "teemip", "TeemIP / iTop"
    SOLARWINDS = "solarwinds", "SolarWinds"
    MANAGEENGINE = "manageengine", "ManageEngine"
    MICROSOFT_IPAM = "microsoft_ipam", "Microsoft IPAM"
    NETBOX = "netbox", "NetBox"
    NAUTOBOT = "nautobot", "Nautobot"
    RALPH = "ralph", "Ralph"
    GENERIC_SQL = "generic_sql", "Generic SQL"
    OTHER = "other", _("Generic / Other IPAM")


class ImportMode(TextChoicesBase):
    HISTORY_ONLY = "history_only", _("History only")
    INVENTORY_HISTORY = "inventory_history", _("Inventory and history")


class JobStatus(TextChoicesBase):
    RUNNING = "running", _("Running")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")
    DRY_RUN = "dry_run", _("Dry run")
    ROLLED_BACK = "rolled_back", _("Rolled back")