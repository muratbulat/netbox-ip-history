import io
from types import SimpleNamespace
from unittest import TestCase

from netbox_ip_history.importers.gestioip import GestioIPImporter
from netbox_ip_history.services.import_service import normalize_record


class GestioIPImportTests(TestCase):
    def setUp(self):
        self.mock_source = SimpleNamespace(
            name="GestioIP",
            slug="gestioip",
            source_type="gestioip",
            source_timezone="Europe/Istanbul",
            field_mapping={},
        )
        self.sample_csv = """IP,hostname,description,Site,type,AI,comment,network,BM,network category, update type,Name,Acik/Kapali,ping
10.10.20.1,GATEWAY,,DC1,,n,,10.10.20.0,22,local,,"gw01","Kapalı",OK
10.10.20.2,LB01,,DC1,,n,,10.10.20.0,22,local,,"LB01","",OK
10.10.20.3,LB02,,DC1,,n,,10.10.20.0,22,local,,"LB02","",OK
10.10.20.70,DHCP-SRV01,DHCP-SRV01,DC1,,y,,10.10.20.0,22,local,,"DHCP-SRV01","Acik",OK
10.10.20.71,DHCP-SRV02,DHCP-SRV02,DC1,,n,,10.10.20.0,22,local,,"DHCP-SRV02","Acik",OK
10.10.20.96,app1.example.org,APP1.EXAMPLE.ORG    ,DC1,,n,,10.10.20.0,22,local,,"APP-NODE01","",OK
10.10.20.97,app2.example.org,APP2.EXAMPLE.ORG    ,DC1,,n,,10.10.20.0,22,local,,"APP-NODE02","",OK
10.10.20.98,Linux,,DC1,,n,,10.10.20.0,22,local,,"","",OK
10.10.20.99,Linux,,DC1,,n,,10.10.20.0,22,local,,"","",OK
10.10.20.100,db01.example.org,DB01.EXAMPLE.ORG,DC1,,n,,10.10.20.0,22,local,,"","",OK
10.10.20.101,vcenter01.example.org,,DC1,,n,,10.10.20.0,22,local,,"VCENTER-SRV","Acik",OK
10.10.20.105,archive.example.org,STORAGE_TCP_80_http,DC1,,n,Node:10.10.20.9610.10.20.97,10.10.20.0,22,local,,"STORAGE_Pool_80","Acik",OK
10.10.20.110,train01.example.org,,DC1,,n,,10.10.20.0,22,local,,"TRAIN-SRV01","",OK
10.10.20.121,node01.example.org,,DC1,,n,,10.10.20.0,22,local,dns,"","",failed
10.10.20.122,node02.example.org,,DC1,,n,,10.10.20.0,22,local,dns,"","",failed
10.10.20.123,node03.example.org,,DC1,,n,,10.10.20.0,22,local,dns,"","",failed
10.10.20.155,vcenter-cluster.example.org,,DC1,,n,,10.10.20.0,22,local,dns,"","",failed"""

    def test_gestioip_csv_import_parsing(self):
        stream = io.StringIO(self.sample_csv)
        importer = GestioIPImporter(self.mock_source, stream)
        records = list(importer.iter_records())

        self.assertEqual(len(records), 17)

        # Check first record: 10.10.20.1
        rec1 = records[0]
        self.assertEqual(rec1["ip_address"], "10.10.20.1")
        self.assertEqual(rec1["hostname"], "GATEWAY")
        self.assertEqual(rec1["prefix_length"], "22")
        self.assertEqual(rec1["site"], "DC1")
        self.assertEqual(rec1["status"], "Kapalı")

        # Check record with Name and hostname: 10.10.20.96
        rec_96 = next(r for r in records if r["ip_address"] == "10.10.20.96")
        self.assertEqual(rec_96["owner_name"], "APP-NODE01")
        self.assertEqual(rec_96["hostname"], "app1.example.org")

        # Test normalization of all records (no exceptions raised)
        for raw in records:
            norm = normalize_record(self.mock_source, raw)
            self.assertTrue(norm["ip_address"].startswith("10.10.20."))
            self.assertEqual(norm["prefix_length"], 22)
            self.assertIn("fingerprint", norm)
