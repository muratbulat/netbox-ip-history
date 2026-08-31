from .base import BaseIPAMImporter
from .capabilities import ImportCapability, SupportLevel
from .dto import SourceInspection


class VendorFileImporter(BaseIPAMImporter):
    display_name = "Generic vendor export"
    support_level = SupportLevel.EXPORT
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.HISTORY_FILE, ImportCapability.ADDRESSES}

    def iter_records(self):
        self.stream.seek(0)
        sample = self.stream.read(512)
        self.stream.seek(0)
        if isinstance(sample, bytes):
            sample = sample.decode("utf-8-sig")
        if sample.lstrip().startswith("[") or sample.lstrip().startswith("{"):
            from .generic_json import GenericJSONImporter
            yield from GenericJSONImporter(self.source, self.stream, self.mapping).iter_records()
        else:
            from .generic_csv import GenericCSVImporter
            yield from GenericCSVImporter(self.source, self.stream, self.mapping).iter_records()

    def inspect(self):
        return SourceInspection(self.display_name, capabilities={cap.value: True for cap in self.capabilities}, available_methods=["export"], warnings=["API and audit history availability depends on the supplied export."])