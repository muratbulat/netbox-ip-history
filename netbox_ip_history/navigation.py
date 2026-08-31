try:
    from django.utils.translation import gettext_lazy as _
except ImportError:
    _ = lambda s: s

try:
    from netbox.plugins import PluginMenu, PluginMenuItem
except ImportError:
    class PluginMenuItem:
        def __init__(self, link, link_text, permissions=None, buttons=None):
            self.link = link
            self.link_text = link_text
            self.permissions = permissions or []
            self.buttons = buttons or ()

    class PluginMenu:
        def __init__(self, label, icon_class=None, groups=()):
            self.label = label
            self.icon_class = icon_class
            self.groups = groups


# Empty menu_items prevents adding duplicate links under NetBox's default "Plugins" sidebar menu
menu_items = ()

# Dedicated top-level "IP History" menu in the NetBox sidebar
menu = PluginMenu(
    label=_("IP History"),
    icon_class="mdi mdi-history",
    groups=(
        (
            _("History & Analysis"),
            (
                PluginMenuItem(
                    link="plugins:netbox_ip_history:history",
                    link_text=_("Timeline & Search"),
                    permissions=["netbox_ip_history.view_historicalipevent"],
                ),
                PluginMenuItem(
                    link="plugins:netbox_ip_history:compare",
                    link_text=_("Source Comparison"),
                    permissions=["netbox_ip_history.view_historicalipevent"],
                ),
            ),
        ),
        (
            _("Data Management"),
            (
                PluginMenuItem(
                    link="plugins:netbox_ip_history:import",
                    link_text=_("Import Data"),
                    permissions=["netbox_ip_history.add_historicalipevent"],
                ),
                PluginMenuItem(
                    link="plugins:netbox_ip_history:import_jobs",
                    link_text=_("Import Jobs"),
                    permissions=["netbox_ip_history.view_importjob"],
                ),
                PluginMenuItem(
                    link="plugins:netbox_ip_history:source_support",
                    link_text=_("Source Support Matrix"),
                    permissions=["netbox_ip_history.view_importsource"],
                ),
            ),
        ),
    ),
)