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


def purge_search_cache() -> int:
    """
    Delete this plugin's entries from NetBox's search cache (extras.CachedValue).

    With ``enable_global_search`` off the indexes above are not registered, but values cached
    while it was on remain and keep matching searches. NetBox renders every result through its
    model's registered index, so one such row makes the whole global search page fail.
    """
    from django.contrib.contenttypes.models import ContentType
    from extras.models import CachedValue

    object_types = list(ContentType.objects.get_for_models(HistoricalIPEvent, ImportSource).values())
    deleted, _ = CachedValue.objects.filter(object_type__in=object_types).delete()
    return deleted
