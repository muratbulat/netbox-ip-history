"""NetBox IP History: unified native and imported IP address lifecycle history."""

from netbox.plugins import PluginConfig

__version__ = "1.0.0"


class NetBoxIPHistoryConfig(PluginConfig):
    name = "netbox_ip_history"
    verbose_name = "NetBox IP History"
    description = "Unified native and imported IP address lifecycle history for NetBox"
    version = __version__
    author = "Murat Bulat"
    base_url = "ip-history"
    min_version = "4.7.0"
    max_version = None
    required_settings = []
    default_settings = {
        "enable_global_search": True,
        "enable_native_event_tracking": True,
        # Record pre-existing ipaddress ObjectChanges (and index them for search) on every migrate.
        "backfill_on_migrate": True,
        # Uploads at or above this size are queued as a background job.
        "background_import_threshold": 5 * 1024 * 1024,
        "max_upload_size": 50 * 1024 * 1024,
    }

    def ready(self):
        super().ready()
        from . import signals  # noqa: F401


config = NetBoxIPHistoryConfig
