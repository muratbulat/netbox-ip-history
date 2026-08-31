from unittest import TestCase

from netbox_ip_history.services.normalize import RecordError, normalize_event_type, normalize_ip, normalize_timestamp


class NormalizeTests(TestCase):
    def test_ipv4_prefix_is_separate(self):
        self.assertEqual(normalize_ip("10.222.1.33/24"), ("10.222.1.33", 24))
        self.assertEqual(normalize_ip(" 192.168.1.1/32 "), ("192.168.1.1", 32))
        self.assertEqual(normalize_ip('"172.16.0.5"'), ("172.16.0.5", None))

    def test_ipv6_equivalent_forms_match(self):
        self.assertEqual(normalize_ip("2001:0db8:0:0:0:0:0:1")[0], normalize_ip("2001:db8::1")[0])
        self.assertEqual(normalize_ip("2001:db8::1/64"), ("2001:db8::1", 64))

    def test_invalid_ip_raises_record_error(self):
        with self.assertRaises(RecordError):
            normalize_ip("")
        with self.assertRaises(RecordError):
            normalize_ip("999.999.999.999")
        with self.assertRaises(RecordError):
            normalize_ip("not-an-ip")

    def test_naive_timestamp_requires_timezone(self):
        with self.assertRaises(RecordError):
            normalize_timestamp("2025-01-01T10:00:00")

    def test_timestamp_parsing_with_timezone(self):
        ts = normalize_timestamp("2025-01-01T10:00:00Z")
        self.assertIsNotNone(ts)
        ts2 = normalize_timestamp("2025-01-01 10:00:00", source_timezone="UTC")
        self.assertIsNotNone(ts2)
        ts3 = normalize_timestamp("01/01/2025", source_timezone="UTC")
        self.assertIsNotNone(ts3)
        ts4 = normalize_timestamp("1704067200", source_timezone="UTC")
        self.assertIsNotNone(ts4)

    def test_event_alias_is_normalized(self):
        self.assertEqual(normalize_event_type("Added"), "created")
        self.assertEqual(normalize_event_type("Delete"), "deleted")
        self.assertEqual(normalize_event_type("Edit"), "updated")
        self.assertEqual(normalize_event_type("DNS"), "updated")
        self.assertEqual(normalize_event_type("Manual"), "imported")
        self.assertEqual(normalize_event_type(""), "imported")