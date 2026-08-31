PLUGINS = [
    "netbox_ip_history",
]

PLUGINS_CONFIG = {
    "netbox_ip_history": {
        # Enable or disable NetBox 4.x global search indexing for IP events and sources
        "enable_global_search": True,
        # Enable or disable real-time tracking of native NetBox IP changes (ObjectChange signal listener)
        "enable_native_event_tracking": True,
    }
}