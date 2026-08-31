from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any


class BaseIPAMImporter(ABC):
    #: True for importers with real, vendor-specific parsing logic. False for
    #: adapters that only declare capabilities and delegate to generic
    #: CSV/JSON sniffing (see RegisteredVendorImporter) — surfaced in the
    #: source support matrix so the UI/API don't overstate integration depth.
    implemented = True

    def __init__(self, source, stream, mapping=None):
        self.source = source
        self.stream = stream
        self.mapping = mapping or source.field_mapping

    def validate_source(self) -> None:
        if not self.source.enabled:
            raise ValueError("Import source is disabled")

    def inspect(self) -> dict[str, Any]:
        return {"fields": [], "source": self.source.name}

    def inspect_source(self):
        return self.inspect()

    @abstractmethod
    def iter_records(self) -> Iterator[dict[str, Any]]:
        raise NotImplementedError

    def iter_inventory(self):
        return self.iter_records()

    def iter_history(self):
        return self.iter_records()

    def normalize_inventory_record(self, record):
        return record

    def normalize_history_record(self, record):
        return record

    def validate_record(self, record):
        return record