from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase

from netbox_ip_history.importers import importer_for, support_matrix


class RegistryTests(TestCase):
    def test_required_adapters_are_registered(self):
        matrix = {row["source_type"] for row in support_matrix()}
        self.assertTrue({"gestioip", "phpipam", "racktables", "generic_json", "generic_sql"}.issubset(matrix))

    def test_vendor_file_adapter_is_inspectable(self):
        source = SimpleNamespace(enabled=True, field_mapping={}, name="RackTables")
        importer = importer_for("racktables")(source, BytesIO(b"ip,event_type\n192.0.2.1,created\n"))
        inspection = importer.inspect_source()
        self.assertEqual(inspection.product, "RackTables")
        self.assertIn("addresses", inspection.capabilities)

    def test_support_matrix_distinguishes_placeholders_from_real_implementations(self):
        matrix = {row["source_type"]: row["implemented"] for row in support_matrix()}
        # Real, vendor-specific parsing logic.
        self.assertTrue(matrix["gestioip"])
        self.assertTrue(matrix["phpipam"])
        self.assertTrue(matrix["generic_csv"])
        self.assertTrue(matrix["generic_json"])
        # Placeholders that only declare capabilities and delegate to generic
        # CSV/JSON sniffing with no vendor-specific logic.
        self.assertFalse(matrix["racktables"])
        self.assertFalse(matrix["glpi"])
        self.assertFalse(matrix["netbox"])
        self.assertFalse(matrix["generic_sql"])
