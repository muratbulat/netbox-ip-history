try:
    from netbox.plugins import get_plugin_config
    SEARCH_ENABLED = get_plugin_config("netbox_ip_history", "enable_global_search", True)
except Exception:
    SEARCH_ENABLED = True

try:
    from netbox.search import SearchIndex, register_search
except ImportError:
    def register_search(cls):
        return cls

    class SearchIndex:
        pass

from .models import HistoricalIPEvent, ImportSource

if SEARCH_ENABLED:
    @register_search
    class HistoricalIPEventIndex(SearchIndex):
        model = HistoricalIPEvent
        fields = (
            ("ip_address", 1000),
            ("hostname", 500),
            ("dns_name", 400),
            ("vrf_name", 300),
            ("owner_name", 200),
            ("description", 100),
        )
        display_attrs = ("ip_address", "event_type", "vrf_name", "hostname", "source")

    @register_search
    class ImportSourceIndex(SearchIndex):
        model = ImportSource
        fields = (
            ("name", 1000),
            ("slug", 500),
            ("description", 100),
        )
        display_attrs = ("name", "source_type", "enabled")
else:
    class HistoricalIPEventIndex:
        model = HistoricalIPEvent

    class ImportSourceIndex:
        model = ImportSource
