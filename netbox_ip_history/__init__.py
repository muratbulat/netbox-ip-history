"""
NetBox IP History Plugin - Unified native and external IP history for NetBox.
"""

try:
    from importlib.metadata import version
    __version__ = version("netbox-ip-history")
except Exception:
    __version__ = "0.3.3"


try:
    from django.utils.translation import gettext_lazy as _
    from netbox.plugins import PluginConfig
except ImportError:
    class PluginConfig:
        pass
    _ = lambda s: s

__all__ = ("NetBoxIPHistoryConfig", "config")


class NetBoxIPHistoryConfig(PluginConfig):
    """
    NetBox plugin configuration for IP History management.
    """

    name = "netbox_ip_history"
    verbose_name = _("NetBox IP History")
    version = __version__
    description = _("Multi-source IPAM history, migration, and audit plugin for NetBox")
    author = "Murat Bulat"
    author_email = "muratbulat@users.noreply.github.com"
    docs_url = "https://github.com/muratbulat/netbox-ip-history/wiki"
    base_url = "ip-history"
    min_version = "4.0.0"
    max_version = "4.99.99"
    default_settings = {
        "enable_global_search": True,
        "enable_native_event_tracking": True,
    }
    required_settings = []

    def ready(self):
        super().ready()
        try:
            from .signals import connect_signals
            connect_signals()
        except Exception:
            pass


config = NetBoxIPHistoryConfig