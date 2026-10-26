from netbox.plugins import get_plugin_config
from netbox.search import SearchIndex

from .models import HistoricalIPEvent, ImportSource


class HistoricalIPEventIndex(SearchIndex):
    model = HistoricalIPEvent
    fields = (
        ("ip_address", 100),
        ("hostname", 300),
        ("dns_name", 300),
        ("owner_name", 400),
        ("mac_address", 500),
        ("vrf_name", 1000),
        ("description", 2000),
    )
    display_attrs = ("event_type", "source", "vrf_name", "hostname", "timestamp")


class ImportSourceIndex(SearchIndex):
    model = ImportSource
    fields = (
        ("name", 100),
        ("slug", 110),
        ("description", 500),
    )
    display_attrs = ("source_type", "enabled")


indexes = (
    [HistoricalIPEventIndex, ImportSourceIndex]
    if get_plugin_config("netbox_ip_history", "enable_global_search")
    else []
)
