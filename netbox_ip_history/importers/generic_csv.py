"""Generic tabular importers: CSV/TSV, JSON/JSON Lines and flat XML exports."""

import json
import re
import xml.etree.ElementTree as ElementTree

from .base import BaseImporter

__all__ = ("GenericCSVImporter", "GenericJSONImporter", "UnsafeXMLError", "iter_json_rows", "iter_xml_rows")

# Any DTD may declare entities (billion laughs / external entity expansion); flat
# record exports never need one, so reject rather than try to sanitize.
_UNSAFE_XML = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


class UnsafeXMLError(ValueError):
    pass


def iter_json_rows(text: str):
    text = text.strip()
    if not text:
        return
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(data, dict):
        data = next((data[key] for key in ("records", "results", "data") if isinstance(data.get(key), list)), [data])
    if not isinstance(data, list):
        raise ValueError("JSON import must be an array, JSON Lines, or an object with a 'records'/'results' list")
    for row in data:
        if not isinstance(row, dict):
            raise ValueError("JSON records must be objects")
        yield row


def iter_xml_rows(text: str):
    """
    Yield flat records from an XML export: each child of the root element is a record and
    its attributes plus simple child elements are the fields.
    """
    if _UNSAFE_XML.search(text):
        raise UnsafeXMLError("XML documents containing DOCTYPE or ENTITY declarations are rejected")
    root = ElementTree.fromstring(text)  # noqa: S314 (DTDs rejected above)
    for element in root:
        row = dict(element.attrib)
        for child in element:
            if len(child) == 0:
                row[child.tag] = (child.text or "").strip()
        if row:
            yield row


class GenericCSVImporter(BaseImporter):
    source_type = "generic_csv"
    display_name = "Generic CSV / TSV"
    formats = ("csv",)

    def iter_records(self):
        for row in self.iter_csv_rows():
            yield self.to_record(row)


class GenericJSONImporter(BaseImporter):
    source_type = "generic_json"
    display_name = "Generic JSON / JSON Lines"
    formats = ("json",)

    def iter_records(self):
        for row in iter_json_rows(self.read_text()):
            yield self.to_record(row)
