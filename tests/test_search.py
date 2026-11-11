"""
Regression tests for the ``enable_global_search`` setting.

Bug: with the setting off, the plugin's search indexes were not registered, but its rows in
NetBox's search cache stayed. NetBox renders every search result through the result model's
registered index, so any leftover row made the whole global search page fail.

These tests set the search registry and the setting explicitly, so they do not depend on how
the host NetBox is configured.
"""

import importlib
from unittest import mock

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.signals import request_started
from django.test import override_settings
from django.urls import reverse
from extras.models import CachedValue
from ipam.models import IPAddress
from netbox.registry import registry
from netbox.search.backends import search_backend
from utilities.testing import TestCase

from netbox_ip_history import search, signals
from netbox_ip_history.models import HistoricalIPEvent, ImportSource

from .helpers import ip_change

PLUGIN_INDEXES = {
    "netbox_ip_history.historicalipevent": search.HistoricalIPEventIndex,
    "netbox_ip_history.importsource": search.ImportSourceIndex,
}


def plugin_config(enabled):
    config = {**settings.PLUGINS_CONFIG.get("netbox_ip_history", {}), "enable_global_search": enabled}
    return {**settings.PLUGINS_CONFIG, "netbox_ip_history": config}


def purge_hook_connected():
    return any(lookup[0] == signals._SEARCH_PURGE_UID for lookup, *_ in request_started.receivers)


class GlobalSearchTestBase(TestCase):
    def setUp(self):
        super().setUp()
        self.user.is_superuser = True
        self.user.save()
        # Start from "search enabled": plugin indexes registered, no purge pending.
        self.patch_registry({**registry["search"], **PLUGIN_INDEXES})
        request_started.disconnect(dispatch_uid=signals._SEARCH_PURGE_UID)
        self.addCleanup(signals.schedule_search_cache_purge)  # Back to the host's own setting.

        self.ip = IPAddress.objects.create(address="192.0.2.70/24")
        ip_change("192.0.2.70/24")
        self.event = HistoricalIPEvent.objects.get(ip_address="192.0.2.70")
        # NetBox defers indexing past the response; cache synchronously for deterministic tests.
        search_backend.cache(self.ip)
        search_backend.cache([self.event])

    def patch_registry(self, indexes):
        patcher = mock.patch.dict(registry["search"], indexes, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def plugin_cache_rows(self):
        object_types = ContentType.objects.get_for_models(HistoricalIPEvent, ImportSource).values()
        return CachedValue.objects.filter(object_type__in=list(object_types))

    def global_search(self):
        return self.client.get(reverse("search"), {"q": "192.0.2.70"})


class GlobalSearchEnabledTests(GlobalSearchTestBase):
    """enable_global_search=True: plugin search keeps working."""

    def test_indexes_are_registered(self):
        self.addCleanup(importlib.reload, search)
        with override_settings(PLUGINS_CONFIG=plugin_config(True)):
            self.assertEqual({idx.model for idx in importlib.reload(search).indexes}, {HistoricalIPEvent, ImportSource})

    def test_no_cache_purge_is_scheduled(self):
        with override_settings(PLUGINS_CONFIG=plugin_config(True)):
            self.assertFalse(signals.schedule_search_cache_purge())
        self.assertFalse(purge_hook_connected())

    def test_global_search_returns_native_and_plugin_results(self):
        response = self.global_search()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ip.get_absolute_url())
        self.assertContains(response, self.event.get_absolute_url())
        self.assertTrue(self.plugin_cache_rows().exists())


class GlobalSearchDisabledTests(GlobalSearchTestBase):
    """enable_global_search=False: only this plugin's search is disabled."""

    def setUp(self):
        super().setUp()  # Cache rows written while search was enabled, as on an upgraded system.
        self.patch_registry({k: v for k, v in registry["search"].items() if k not in PLUGIN_INDEXES})

    def test_no_indexes_are_registered(self):
        self.addCleanup(importlib.reload, search)
        with override_settings(PLUGINS_CONFIG=plugin_config(False)):
            self.assertEqual(importlib.reload(search).indexes, [])

    def test_cache_purge_is_scheduled(self):
        with override_settings(PLUGINS_CONFIG=plugin_config(False)):
            self.assertTrue(signals.schedule_search_cache_purge())
        self.assertTrue(purge_hook_connected())

    def test_leftover_cache_rows_break_native_search_without_the_fix(self):
        """Reproduces the root cause: NetBox renders results through the (missing) index."""
        with self.assertRaises(AttributeError):
            self.global_search()

    def test_first_request_purges_plugin_cache_and_native_search_works(self):
        with override_settings(PLUGINS_CONFIG=plugin_config(False)):
            signals.schedule_search_cache_purge()

        response = self.global_search()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ip.get_absolute_url())
        self.assertNotContains(response, self.event.get_absolute_url())
        self.assertFalse(self.plugin_cache_rows().exists())
        self.assertFalse(purge_hook_connected(), "the purge runs once per process")

    def test_purge_keeps_other_cache_entries(self):
        ip_type = ContentType.objects.get_for_model(IPAddress)
        before = CachedValue.objects.filter(object_type=ip_type).count()
        self.assertGreater(search.purge_search_cache(), 0)
        self.assertEqual(CachedValue.objects.filter(object_type=ip_type).count(), before)

    def test_plugin_writes_no_new_cache_entries(self):
        search.purge_search_cache()
        with self.captureOnCommitCallbacks(execute=True):
            ip_change("192.0.2.71/24")
        self.assertFalse(self.plugin_cache_rows().exists())
