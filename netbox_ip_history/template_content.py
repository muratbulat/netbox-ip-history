from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _
from netbox.plugins import PluginTemplateExtension


class IPAddressHistoryButton(PluginTemplateExtension):
    """'IP History' button on the IP address page, linking to the full cross-source timeline."""

    models = ["ipam.ipaddress"]

    def buttons(self):
        request = self.context["request"]
        if not request.user.has_perm("netbox_ip_history.view_historicalipevent"):
            return ""
        ip = self.context["object"].address.ip
        return format_html(
            '<a href="{}?ip={}" class="btn btn-primary"><i class="mdi mdi-history" aria-hidden="true"></i> {}</a>',
            reverse("plugins:netbox_ip_history:timeline"),
            ip,
            _("IP History"),
        )


template_extensions = [IPAddressHistoryButton]
