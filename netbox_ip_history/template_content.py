from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.translation import gettext as _
from netbox.plugins import PluginTemplateExtension


class IPAddressHistoryButton(PluginTemplateExtension):
    """'IP History' button on the IP address page: the cross-source timeline of this address in its VRF."""

    models = ["ipam.ipaddress"]

    def buttons(self):
        request = self.context["request"]
        if not request.user.has_perm("netbox_ip_history.view_historicalipevent"):
            return ""
        address = self.context["object"]
        query = urlencode({"ip": address.address.ip, "vrf": address.vrf.name if address.vrf else "Global"})
        return format_html(
            '<a href="{}?{}" class="btn btn-primary"><i class="mdi mdi-history" aria-hidden="true"></i> {}</a>',
            reverse("plugins:netbox_ip_history:timeline"),
            query,
            _("IP History"),
        )


template_extensions = [IPAddressHistoryButton]
