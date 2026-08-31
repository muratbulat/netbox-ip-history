import json

from .base import BaseIPAMImporter
from .capabilities import ImportCapability, SupportLevel
from .generic_csv import DEFAULT_FIELD_ALIASES


class GenericJSONImporter(BaseIPAMImporter):
    display_name = "Generic JSON / JSONL"
    support_level = SupportLevel.EXPORT
    capabilities = {ImportCapability.INVENTORY_FILE, ImportCapability.HISTORY_FILE, ImportCapability.ADDRESSES}

    def iter_records(self):
        if hasattr(self.stream, "seek"):
            self.stream.seek(0)
        try:
            data = json.load(self.stream)
        except json.JSONDecodeError:
            if hasattr(self.stream, "seek"):
                self.stream.seek(0)
            data = [json.loads(line) for line in self.stream if line.strip()]
        if isinstance(data, dict) and isinstance(data.get("records"), list):
            data = data["records"]
        if not isinstance(data, list):
            raise ValueError("JSON import must contain an array, JSON Lines, or exchange-format records")

        mapping = self.mapping or getattr(self.source, "field_mapping", {}) or {}

        for raw_row in data:
            if not isinstance(raw_row, dict):
                raise ValueError("JSON records must be objects")

            clean_row = {}
            for k, v in raw_row.items():
                if k is None:
                    continue
                clean_k = str(k).strip().lower().replace(" ", "_").replace("-", "_")
                val = v.strip() if isinstance(v, str) else v
                clean_row[clean_k] = val

            record = {}
            # 1. Apply explicit mapping if provided
            for target, column in mapping.items():
                norm_col = str(column).strip().lower().replace(" ", "_").replace("-", "_")
                if norm_col in clean_row and clean_row[norm_col] != "":
                    record[target] = clean_row[norm_col]

            # 2. Fill missing targets using DEFAULT_FIELD_ALIASES
            for target, aliases in DEFAULT_FIELD_ALIASES.items():
                if target not in record or not record[target]:
                    for alias in aliases:
                        norm_alias = alias.replace(" ", "_").replace("-", "_")
                        if norm_alias in clean_row and clean_row[norm_alias] != "":
                            record[target] = clean_row[norm_alias]
                            break

            record["raw_data"] = raw_row
            yield record