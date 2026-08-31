try:
    from netbox.plugins import PluginTemplateExtension
except ImportError:
    class PluginTemplateExtension:
        models = []

        def __init__(self, context):
            self.context = context

        def render(self, template_name, extra_context=None):
            return ""


class IPAddressHistoryExtension(PluginTemplateExtension):
    """
    Adds the upper "IP History" action button to NetBox's own IP Address
    detail page (buttons()) — the plugin's documented, supported mechanism
    for injecting an action alongside Edit/Delete/etc. This is intentionally
    the ONLY hook implemented here: right_page() (a large "Audit changes,
    previous assignments, DNS history..." info panel) was removed as
    redundant with both this button and the native "IP History" tab
    (views.IPAddressHistoryTabView, registered via register_model_view) and
    must not be restored.
    """
    models = ["ipam.ipaddress"]

    def _has_permission(self):
        request = self.context.get("request") if isinstance(self.context, dict) else getattr(self.context, "get", lambda k, d=None: None)("request")
        if request and hasattr(request, "user"):
            user = request.user
            if not getattr(user, "is_authenticated", False) or not user.has_perm("netbox_ip_history.view_historicalipevent"):
                return False
        return True

    def buttons(self):
        if not self._has_permission():
            return ""
        return self.render("netbox_ip_history/inc/ipaddress_buttons.html")


template_extensions = [IPAddressHistoryExtension]
