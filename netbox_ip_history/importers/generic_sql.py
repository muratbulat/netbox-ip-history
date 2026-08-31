from .base import BaseIPAMImporter
from .capabilities import ImportCapability, SupportLevel
from .dto import SourceInspection


class GenericSQLImporter(BaseIPAMImporter):
    display_name = "Generic SQL / legacy IPAM"
    support_level = SupportLevel.EXPERIMENTAL
    #: No read-only database connector exists yet; iter_records() intentionally
    #: refuses to run rather than silently returning nothing.
    implemented = False
    capabilities = {ImportCapability.READONLY_DATABASE, ImportCapability.ADDRESSES, ImportCapability.PREFIXES, ImportCapability.HISTORY}

    def inspect(self):
        return SourceInspection(self.display_name, capabilities={cap.value: True for cap in self.capabilities}, available_methods=["readonly_database"], warnings=["Only administrator-defined, parameterized table/view mappings are supported."])

    def iter_records(self):
        raise ValueError("Configure a read-only database connector and field mapping before using generic SQL")