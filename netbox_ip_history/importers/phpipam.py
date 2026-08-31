from .base import BaseIPAMImporter
from .generic_csv import GenericCSVImporter
from .generic_json import GenericJSONImporter
from .capabilities import ImportCapability, SupportLevel


class PhpIPAMImporter(BaseIPAMImporter):
    """Adapter for phpIPAM exports; API/DB clients emit the same record contract.

    Delegates parsing to the generic CSV/JSON importer with phpIPAM's column
    aliases pre-seeded, while remaining a real BaseIPAMImporter subclass (so
    isinstance()/type checks on instances behave as expected).
    """
    aliases = {"ip": "ip_address", "subnet": "prefix_length", "hostname": "hostname", "dns": "dns_name", "owner": "owner_name", "device": "device_name", "note": "description", "action": "source_event_type", "date": "timestamp", "username": "source_username", "mac": "mac_address"}
    display_name = "phpIPAM"
    support_level = SupportLevel.EXPORT
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.HISTORY_FILE, ImportCapability.ADDRESSES, ImportCapability.PREFIXES}

    def __init__(self, source, stream, mapping=None, format="json"):
        super().__init__(source, stream, mapping)
        defaults = {target: key for key, target in self.aliases.items()}
        self.mapping = defaults | self.mapping
        delegate_cls = GenericJSONImporter if format == "json" else GenericCSVImporter
        self._delegate = delegate_cls(source, stream, self.mapping)

    def iter_records(self):
        yield from self._delegate.iter_records()

    def inspect(self):
        return self._delegate.inspect()