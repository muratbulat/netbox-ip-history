from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

menu = PluginMenu(
    label=_("IP History"),
    icon_class="mdi mdi-history",
    groups=(
        (
            _("History"),
            (
                PluginMenuItem(
                    link="plugins:netbox_ip_history:timeline",
                    link_text=_("Timeline"),
                    permissions=["netbox_ip_history.view_historicalipevent"],
                ),
                PluginMenuItem(
                    link="plugins:netbox_ip_history:compare",
                    link_text=_("Source Comparison"),
                    permissions=["netbox_ip_history.view_historicalipevent"],
                ),
                PluginMenuItem(
                    link="plugins:netbox_ip_history:historicalipevent_list",
                    link_text=_("Events"),
                    permissions=["netbox_ip_history.view_historicalipevent"],
                ),
            ),
        ),
        (
            _("Import"),
            (
                PluginMenuItem(
                    link="plugins:netbox_ip_history:import",
                    link_text=_("Import History"),
                    permissions=["netbox_ip_history.add_historicalipevent"],
                ),
                PluginMenuItem(
                    link="plugins:netbox_ip_history:importjob_list",
                    link_text=_("Import Jobs"),
                    permissions=["netbox_ip_history.view_importjob"],
                ),
                PluginMenuItem(
                    link="plugins:netbox_ip_history:importsource_list",
                    link_text=_("Sources"),
                    permissions=["netbox_ip_history.view_importsource"],
                    buttons=(
                        PluginMenuButton(
                            link="plugins:netbox_ip_history:importsource_add",
                            title=_("Add"),
                            icon_class="mdi mdi-plus-thick",
                            permissions=["netbox_ip_history.add_importsource"],
                        ),
                    ),
                ),
                PluginMenuItem(
                    link="plugins:netbox_ip_history:source_support",
                    link_text=_("Supported Formats"),
                    permissions=["netbox_ip_history.view_importsource"],
                ),
            ),
        ),
    ),
)
