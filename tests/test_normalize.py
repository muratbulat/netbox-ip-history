from datetime import UTC, datetime

from django.test import SimpleTestCase, override_settings

from netbox_ip_history.choices import EventTypeChoices
from netbox_ip_history.services.normalize import (
    RecordError,
    fingerprint,
    normalize_event_type,
    normalize_ip,
    normalize_timestamp,
    normalize_vrf,
)


class NormalizeIPTests(SimpleTestCase):
    def test_ipv4(self):
        self.assertEqual(normalize_ip("192.0.2.1"), ("192.0.2.1", None))
        self.assertEqual(normalize_ip(" '192.0.2.1/24' "), ("192.0.2.1", 24))

    def test_ipv6_is_canonicalized(self):
        self.assertEqual(normalize_ip("2001:0db8:0000::0001"), ("2001:db8::1", None))
        self.assertEqual(normalize_ip("2001:DB8::1/64"), ("2001:db8::1", 64))

    def test_integer_encoded_address(self):
        self.assertEqual(normalize_ip("3221225985"), ("192.0.2.1", None))

    def test_invalid_input_raises(self):
        for value in ("", None, "192.0.2.256", "not-an-ip", "2001:db8::zz", "192.0.2.1/33", "12"):
            with self.subTest(value=value), self.assertRaises(RecordError):
                normalize_ip(value)


@override_settings(TIME_ZONE="UTC")
class NormalizeTimestampTests(SimpleTestCase):
    def test_iso_with_offset(self):
        self.assertEqual(
            normalize_timestamp("2026-01-05T12:00:00+03:00"), datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
        )

    def test_naive_requires_source_timezone(self):
        with self.assertRaises(RecordError):
            normalize_timestamp("2026-01-05 12:00:00")
        self.assertEqual(
            normalize_timestamp("05.01.2026 12:00", "Europe/Istanbul"), datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
        )

    def test_epoch(self):
        self.assertEqual(normalize_timestamp("0", "UTC"), datetime(1970, 1, 1, tzinfo=UTC))

    def test_missing_uses_default(self):
        default = datetime(2026, 1, 1, tzinfo=UTC)
        self.assertEqual(normalize_timestamp("", default=default), default)

    def test_garbage_raises(self):
        with self.assertRaises(RecordError):
            normalize_timestamp("yesterday", "UTC")


class NormalizeMiscTests(SimpleTestCase):
    def test_event_type_aliases(self):
        self.assertEqual(normalize_event_type("Added"), EventTypeChoices.CREATED)
        self.assertEqual(normalize_event_type("removed"), EventTypeChoices.DELETED)
        self.assertEqual(normalize_event_type("Status Changed"), EventTypeChoices.STATUS_CHANGED)
        self.assertEqual(normalize_event_type(""), EventTypeChoices.IMPORTED)
        self.assertEqual(normalize_event_type("frobnicated"), EventTypeChoices.IMPORTED)

    def test_vrf_global_spellings(self):
        for value in ("", "Global", "GLOBAL", "default", None, "---"):
            self.assertEqual(normalize_vrf(value), "")
        self.assertEqual(normalize_vrf(" BLUE "), "BLUE")

    def test_fingerprint_is_stable_and_source_scoped(self):
        record = {"ip_address": "192.0.2.1", "timestamp": "t", "event_type": "created"}
        self.assertEqual(fingerprint("a", record), fingerprint("a", dict(record)))
        self.assertNotEqual(fingerprint("a", record), fingerprint("b", record))
