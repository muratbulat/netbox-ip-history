import io
from types import SimpleNamespace
from unittest import TestCase

from netbox_ip_history.importers.gestioip import GestioIPImporter
from netbox_ip_history.services.import_service import normalize_record


class GestioIPAuditTests(TestCase):
    def setUp(self):
        self.mock_source = SimpleNamespace(
            name="GestioIP Audit",
            slug="gestioip-audit",
            source_type="gestioip",
            source_timezone="Europe/Istanbul",
            field_mapping={},
        )
        self.sample_audit_csv = """"id","event","user","event_class","event_type","update_type_audit","date","remote_host","client_id"
1,"10.0.26.0/24,vlan26,DC1,Prod,---,n, ",admin,2,17,1,1629961554,"192.168.100.50",1
2,"10.0.26.0/24,---,DC1,Prod,---,n",admin,2,16,1,1629963625,"192.168.100.50",1
3,vlan26,admin,5,39,1,1629963655,"192.168.100.50",1
4,local,admin,5,9,1,1629963730,"192.168.100.50",1
14,"10.0.80.0/24,vlan80,DC1,test,---,n, ",admin,2,17,1,1629963880,"192.168.100.50",1
15,"10.0.80.1: ---,---,---,---,n,---,---,--- -> dc01,---,DC1,---,n,---,---,---",admin,1,15,1,1629964825,"192.168.100.50",1
16,"10.0.80.1: dc01,---,DC1,---,n,---,---,--- -> dc01,test dhcp server and dc,DC1,---,n,---,---,---",admin,1,1,1,1629964855,"192.168.100.50",1
18,"10.0.80.1: down -> up",admin,1,100,6,1629968149,"192.168.100.50",1
19,"10.0.80.10: unknown,---,DC1,---,---",admin,1,15,6,1629968149,"192.168.100.50",1
23,"10.0.80.16: app-test.example.com,---,DC1,---,---",admin,1,15,6,1629968149,"192.168.100.50",1
148,"10.0.80.10/dc01,,---,---,---,'n'",admin,1,15,10,1629979043,"192.168.100.50",1
330,"10.0.80.10/dc01,test dhcp server and dc,---,---,10.0.22.120,'n'",admin,1,15,10,1629979965,"192.168.100.50",1
337,"10.0.80.17/APP-SRV01,Test User - Infra Admin,---,---,10.0.22.120,'n'",admin,1,15,10,1629979965,"192.168.100.50",1
348,"10.0.80.125/DB-PROD01,Project Coordinator VM,---,---,10.0.22.120,'n'",admin,1,15,10,1629979968,"192.168.100.50",1
512,"10.0.80.226: down -> up",admin,1,100,6,1629980213,"192.168.100.50",1"""

    def test_audit_log_parsing(self):
        stream = io.StringIO(self.sample_audit_csv)
        importer = GestioIPImporter(self.mock_source, stream)
        records = list(importer.iter_records())

        # System rows (3: vlan26, 4: local) should be skipped, leaving 13 IP/subnet records
        self.assertEqual(len(records), 13)

        # Check row 15 (10.0.80.1 creation)
        rec_15 = next(r for r in records if r["source_record_id"] == "15")
        self.assertEqual(rec_15["ip_address"], "10.0.80.1")
        self.assertEqual(rec_15["hostname"], "dc01")
        self.assertEqual(rec_15["site"], "DC1")
        self.assertEqual(rec_15["event_type"], "created")

        # Check row 16 (10.0.80.1 description update)
        rec_16 = next(r for r in records if r["source_record_id"] == "16")
        self.assertEqual(rec_16["ip_address"], "10.0.80.1")
        self.assertEqual(rec_16["description"], "test dhcp server and dc")

        # Check row 18 (10.0.80.1 status change)
        rec_18 = next(r for r in records if r["source_record_id"] == "18")
        self.assertEqual(rec_18["ip_address"], "10.0.80.1")
        self.assertEqual(rec_18["status"], "up")
        self.assertEqual(rec_18["event_type"], "status_changed")

        # Check row 337 (10.0.80.17 with owner)
        rec_337 = next(r for r in records if r["source_record_id"] == "337")
        self.assertEqual(rec_337["ip_address"], "10.0.80.17")
        self.assertEqual(rec_337["hostname"], "APP-SRV01")
        self.assertEqual(rec_337["description"], "Test User - Infra Admin")

        # Normalize all records and verify timestamps and fingerprints
        for raw in records:
            norm = normalize_record(self.mock_source, raw)
            self.assertTrue(norm["ip_address"].startswith("10.0."))
            self.assertIsNotNone(norm["timestamp"])
            self.assertIn("fingerprint", norm)
