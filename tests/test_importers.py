import io
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from netbox_ip_history.importers import IMPORTERS, importer_for, support_matrix
from netbox_ip_history.importers.generic_csv import GenericCSVImporter, UnsafeXMLError, iter_xml_rows
from netbox_ip_history.importers.gestioip import GestioIPImporter, parse_gestioip_audit_event
from netbox_ip_history.importers.infoblox import InfobloxImporter
from netbox_ip_history.importers.netbox_export import NetBoxExportImporter
from netbox_ip_history.importers.phpipam import PhpIPAMImporter
from netbox_ip_history.importers.vendor_file import VendorFileImporter

FIXTURES = Path(__file__).parent / "fixtures"


def source(source_type="generic_csv", mapping=None):
    return SimpleNamespace(
        name=source_type, slug=source_type, source_type=source_type, field_mapping=mapping or {}, source_timezone="UTC"
    )


def records(importer_class, fixture, **kwargs):
    stream = io.BytesIO((FIXTURES / fixture).read_bytes())
    return list(importer_class(source(importer_class.source_type), stream, **kwargs).iter_records())


class RegistryTests(SimpleTestCase):
    def test_dedicated_and_profiled_sources_are_registered(self):
        for source_type in ("gestioip", "phpipam", "infoblox", "netbox_export", "racktables", "glpi", "other"):
            self.assertIn(source_type, IMPORTERS)

    def test_profiled_sources_use_generic_parsing(self):
        self.assertTrue(issubclass(importer_for("racktables"), VendorFileImporter))
        self.assertEqual(importer_for("racktables").display_name, "RackTables")
        self.assertIs(importer_for("unknown-type"), VendorFileImporter)

    def test_support_matrix_distinguishes_native_from_generic(self):
        levels = {row["source_type"]: row["support_level"] for row in support_matrix()}
        for native in ("gestioip", "phpipam", "infoblox", "netbox_export"):
            self.assertEqual(levels[native], "native")
        self.assertEqual(levels["racktables"], "generic")


class GenericImporterTests(SimpleTestCase):
    def test_csv_aliases_and_raw_data(self):
        rows = records(GenericCSVImporter, "generic_history.csv")
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["ip_address"], "192.0.2.10")
        self.assertEqual(rows[0]["hostname"], "device-01.example.com")
        self.assertEqual(rows[0]["source_username"], "admin")
        self.assertEqual(rows[0]["raw_data"]["ip"], "192.0.2.10")

    def test_explicit_mapping_wins_over_aliases(self):
        stream = io.StringIO("addr,host,name\n192.0.2.1,device-01.example.com,device-01\n")
        importer = GenericCSVImporter(source(mapping={"hostname": "name", "ip_address": "addr"}), stream)
        (row,) = importer.iter_records()
        self.assertEqual(row["hostname"], "device-01")

    def test_semicolon_delimiter(self):
        importer = GenericCSVImporter(source(), io.StringIO("ip;hostname\n192.0.2.1;device-01\n"), delimiter=";")
        self.assertEqual(next(importer.iter_records())["hostname"], "device-01")

    def test_xml_rows(self):
        rows = list(iter_xml_rows((FIXTURES / "vendor_export.xml").read_text()))
        self.assertEqual(rows[0], {"ip": "198.51.100.7", "hostname": "device-01.example.com", "action": "added",
                                   "date": "2026-06-01T00:00:00+00:00"})
        self.assertEqual(rows[1]["hostname"], "device-02.example.com")

    def test_xml_entity_declarations_are_rejected(self):
        payloads = (
            '<!DOCTYPE x [<!ENTITY a "aaaa">]><x><r ip="&a;"/></x>',
            '<?xml version="1.0"?><!DOCTYPE x SYSTEM "file:///etc/hostname"><x/>',
            '<x><!ENTITY b "c"></x>',
        )
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(UnsafeXMLError):
                list(iter_xml_rows(payload))

    def test_vendor_file_sniffs_format(self):
        cls = importer_for("bluecat")
        for content in (
            b"ip,hostname\n198.51.100.7,device-01\n",
            b'[{"ip": "198.51.100.7", "hostname": "device-01"}]',
            b'<export><a ip="198.51.100.7" hostname="device-01"/></export>',
        ):
            with self.subTest(content=content):
                (row,) = cls(source("bluecat"), io.BytesIO(content)).iter_records()
                self.assertEqual((row["ip_address"], row["hostname"]), ("198.51.100.7", "device-01"))


class GestioIPTests(SimpleTestCase):
    def test_audit_log(self):
        rows = records(GestioIPImporter, "gestioip_audit.csv")
        self.assertEqual(len(rows), 4, "the VLAN audit entry is not an IP event")
        created, changed, status, network = rows
        self.assertEqual(
            (created["event_type"], created["hostname"], created["site"]), ("created", "device-01", "site-a")
        )
        self.assertEqual((changed["event_type"], changed["hostname"]), ("updated", "device-02"))
        self.assertEqual((status["event_type"], status["status"]), ("status_changed", "down"))
        self.assertEqual((network["ip_address"], network["prefix_length"]), ("198.51.100.0", 24))
        self.assertEqual(created["source_record_id"], "101")
        self.assertEqual(created["source_username"], "admin")

    def test_inventory(self):
        rows = records(GestioIPImporter, "gestioip_inventory.csv")
        self.assertEqual(rows[0]["owner_name"], "device-01")
        self.assertEqual(rows[0]["prefix_length"], "24")
        self.assertEqual(rows[0]["source_scope_identifier"], "192.0.2.0")

    def test_audit_event_patterns(self):
        cases = {
            "2001:db8::1: up -> down": ("2001:db8::1", "status_changed"),
            "192.0.2.5/device-01,desc,site-a": ("192.0.2.5", "updated"),
            "192.0.2.6": ("192.0.2.6", "updated"),
        }
        for text, (ip, event_type) in cases.items():
            with self.subTest(text=text):
                parsed = parse_gestioip_audit_event(text)
                self.assertEqual((parsed["ip_address"], parsed["event_type"]), (ip, event_type))
        self.assertIsNone(parse_gestioip_audit_event("entries older than 30 days deleted"))


class PhpIPAMTests(SimpleTestCase):
    def test_json_api_envelope(self):
        rows = records(PhpIPAMImporter, "phpipam_history.json", format="json")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["mac_address"], "00:00:5e:00:53:01")
        self.assertEqual(rows[0]["prefix_length"], "24")
        self.assertEqual(rows[1]["ip_address"], "3405803781")
        self.assertEqual(rows[1]["timestamp"], "2026-03-04T17:18:00+00:00")
        self.assertEqual(rows[1]["description"], "moved")


class InfobloxTests(SimpleTestCase):
    def test_sectioned_csv(self):
        rows = records(InfobloxImporter, "infoblox_nios.csv")
        addresses = [(r["ip_address"], r["source_event_type"]) for r in rows]
        self.assertEqual(
            addresses,
            [
                ("192.0.2.40", "hostrecord"),
                ("192.0.2.41", "hostrecord"),
                ("2001:db8::40", "hostrecord"),
                ("192.0.2.42", "fixedaddress"),
                ("192.0.2.43", "arecord"),
            ],
        )
        self.assertEqual(rows[0]["hostname"], "device-01.example.com")
        self.assertEqual(rows[0]["description"], "lab host")
        self.assertEqual(rows[3]["mac_address"], "00:00:5e:00:53:42")
        self.assertEqual(rows[3]["vrf_name"], "default")
        self.assertEqual(len({r["source_record_id"] for r in rows}), 5)


class NetBoxExportTests(SimpleTestCase):
    def test_only_ipaddress_changes_are_imported(self):
        rows = records(NetBoxExportImporter, "netbox_changelog.json")
        self.assertEqual([r["source_record_id"] for r in rows], ["501", "502"])
        self.assertEqual(rows[0]["ip_address"], "2001:db8::50")
        self.assertEqual(rows[0]["event_type"], "created")
        self.assertEqual(rows[0]["dns_name"], "device-01.example.com")
        self.assertEqual(rows[1]["event_type"], "status_changed")
        self.assertEqual(rows[1]["vrf_name"], "")

    def test_remote_object_ids_are_not_resolved_locally(self):
        # SimpleTestCase forbids database access: any local lookup of remote IDs would raise.
        rows = records(NetBoxExportImporter, "netbox_changelog.json")
        self.assertEqual(rows[1]["owner_name"], "")
