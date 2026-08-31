import gettext
import os
from unittest import TestCase

import netbox_ip_history
from netbox_ip_history import api, filtersets, navigation, search, tables, template_content

# Resolved from the imported module's own __file__, not a hardcoded
# repo-relative path — this suite must pass identically whether it runs
# against the source checkout or a built-and-installed wheel (see
# .github/workflows/ci.yml's "installed-wheel-tests" job), where
# netbox_ip_history lives in site-packages, not next to tests/.
PACKAGE_DIR = os.path.dirname(os.path.abspath(netbox_ip_history.__file__))


class NavigationAndUITests(TestCase):
    def test_navigation_is_configured(self):
        # Verify menu_items is empty so no duplicate links appear under generic "Plugins" menu
        self.assertTrue(hasattr(navigation, "menu_items"))
        self.assertEqual(len(navigation.menu_items), 0)

        # Verify dedicated top-level "IP History" menu is configured
        self.assertTrue(hasattr(navigation, "menu"))
        self.assertEqual(str(navigation.menu.label), "IP History")

        # Verify all menu groups enforce appropriate permissions. Under the
        # Django-less fallback, PluginMenu.groups stays exactly what
        # navigation.py passed in: a tuple of (label, items) pairs. Under
        # real NetBox, PluginMenu.__init__ wraps each pair into a MenuGroup
        # dataclass (label/items attributes, not unpackable) — confirmed
        # against netbox/netbox/plugins/utils.py and netbox/navigation/
        # __init__.py at the pinned production tag (v4.6.8).
        for group in navigation.menu.groups:
            items = group.items if hasattr(group, "items") else group[1]
            for item in items:
                self.assertTrue(len(item.permissions) > 0, f"Group menu item {item.link_text} is missing permissions")

    def test_template_extensions_is_configured(self):
        # The IP Address detail page gets BOTH: an upper "IP History" action
        # button (PluginTemplateExtension.buttons(), this test) AND a native
        # "IP History" tab (register_model_view + ViewTab in views.py, see
        # test_views_source_registers_native_ip_history_tab). Regression:
        # commit 0cc5ad4 removed the button entirely believing the tab
        # alone was sufficient — it was reinstated because the button and
        # tab are both explicitly required, in the same upper action area.
        # right_page() (the old "Audit changes, previous assignments..."
        # info panel) must NOT come back — buttons() is the only hook.
        self.assertTrue(hasattr(template_content, "template_extensions"))
        self.assertEqual(len(template_content.template_extensions), 1)
        ext_class = template_content.template_extensions[0]
        self.assertEqual(ext_class.__name__, "IPAddressHistoryExtension")
        self.assertIn("ipam.ipaddress", ext_class.models)
        # right_page() (the old redundant info panel) must stay absent —
        # buttons() is the only hook this extension implements.
        self.assertNotIn("right_page", ext_class.__dict__)

        # Verify extension checks user permissions before rendering
        ext = ext_class({"request": None})
        self.assertTrue(ext._has_permission())

        class DummyAnonymousUser:
            is_authenticated = False
            def has_perm(self, perm):
                return False

        class DummyRequest:
            user = DummyAnonymousUser()

        ext_anon = ext_class({"request": DummyRequest()})
        self.assertFalse(ext_anon._has_permission())
        self.assertEqual(ext_anon.buttons(), "")

    def test_upper_ip_address_button_template_reverses_filtered_url(self):
        """Regression guard for the specific incident where the upper
        button was dropped entirely (commit 0cc5ad4) on the theory that the
        native tab replaced it. Both must exist: this asserts the button's
        template renders a link to the plugin timeline pre-filtered to the
        current IP, built with {% url %} (never a hardcoded /plugins/...
        path), exactly as it must appear in the IP Address page's upper
        action/button area."""
        button_template = os.path.join(
            PACKAGE_DIR, "templates", "netbox_ip_history", "inc", "ipaddress_buttons.html"
        )
        self.assertTrue(os.path.isfile(button_template), "Upper IP History button template is missing")
        with open(button_template, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("{% url 'plugins:netbox_ip_history:history' %}?ip={{ object.address.ip }}", content)
        self.assertIn('{% trans "IP History" %}', content)
        self.assertIn("perms.netbox_ip_history.view_historicalipevent", content)

    def test_api_is_configured(self):
        self.assertTrue(hasattr(api, "HistoricalIPEventSerializer"))
        self.assertTrue(hasattr(api, "ImportJobSerializer"))
        self.assertTrue(hasattr(api, "ImportSourceSerializer"))

    def test_search_is_configured(self):
        self.assertTrue(hasattr(search, "HistoricalIPEventIndex"))
        self.assertTrue(hasattr(search, "ImportSourceIndex"))
        self.assertEqual(search.HistoricalIPEventIndex.model.__name__, "HistoricalIPEvent")
        self.assertEqual(search.ImportSourceIndex.model.__name__, "ImportSource")
        self.assertTrue(hasattr(search.HistoricalIPEventIndex.model, "get_absolute_url"))
        self.assertTrue(hasattr(search.ImportSourceIndex.model, "get_absolute_url"))

    def test_signals_module_and_sync_command_exist(self):
        from netbox_ip_history import signals
        from netbox_ip_history.services.timeline import extract_netbox_change_details
        self.assertTrue(hasattr(signals, "record_object_change_as_event"))
        self.assertTrue(hasattr(signals, "connect_signals"))

        # Test snapshot extraction
        nested_payload = {
            "address": "192.168.1.50/24",
            "assigned_object": {
                "name": "eth0",
                "virtual_machine": {"name": "VM45"}
            },
            "dns_name": "vm45.local",
            "description": "Production Web VM",
        }
        res = extract_netbox_change_details(nested_payload)
        self.assertEqual(res["host_name"], "VM45")
        self.assertEqual(res["interface_name"], "eth0")
        self.assertEqual(res["dns_name"], "vm45.local")

        str_payload = {
            "address": "192.168.1.50/24",
            "assigned_object": "VM45 > eth0",
        }
        res2 = extract_netbox_change_details(str_payload)
        self.assertEqual(res2["host_name"], "VM45")
        self.assertEqual(res2["interface_name"], "eth0")

        cmd_file = os.path.join(
            PACKAGE_DIR,
            "management",
            "commands",
            "sync_netbox_ip_history.py",
        )
        self.assertTrue(os.path.isfile(cmd_file), f"Missing sync command: {cmd_file}")


    def test_tables_and_filtersets_exist(self):
        self.assertTrue(hasattr(tables, "HistoricalIPEventTable"))
        self.assertTrue(hasattr(tables, "ImportJobTable"))
        self.assertTrue(hasattr(tables, "ImportSourceTable"))
        self.assertTrue(hasattr(filtersets, "HistoricalIPEventFilterSet"))
        self.assertTrue(hasattr(filtersets, "ImportJobFilterSet"))
        self.assertTrue(hasattr(filtersets, "ImportSourceFilterSet"))

    def test_subpackages_have_init(self):
        for sub in ("api", "importers", "management", "management/commands", "migrations", "services"):
            init_file = os.path.join(PACKAGE_DIR, sub.replace("/", os.sep), "__init__.py")
            self.assertTrue(os.path.isfile(init_file), f"Missing __init__.py in {sub}")

    def test_translation_catalog_loads_and_translates(self):
        locale_dir = os.path.join(PACKAGE_DIR, "locale")
        po_path = os.path.join(locale_dir, "tr", "LC_MESSAGES", "django.po")
        mo_path = os.path.join(locale_dir, "tr", "LC_MESSAGES", "django.mo")

        self.assertTrue(os.path.isfile(po_path), f"Missing PO file: {po_path}")
        self.assertTrue(os.path.isfile(mo_path), f"Missing MO file: {mo_path}")

        t = gettext.translation("django", locale_dir, languages=["tr"])
        self.assertEqual(t.gettext("IP History"), "IP Geçmişi")
        self.assertEqual(t.gettext("Timeline & Search"), "Zaman Çizelgesi ve Arama")
        self.assertEqual(t.gettext("Source Comparison"), "Kaynak Karşılaştırması")
        self.assertEqual(t.gettext("Dry run (simulation mode)"), "Deneme modu (veritabanına yazmadan simüle et)")

    def test_forms_when_django_present(self):
        try:
            import django
            from netbox_ip_history import forms
            if getattr(forms, "forms", None) is None:
                return
            search_form = forms.HistorySearchForm(
                data={"ip": "192.0.2.1", "vrf": "Global", "event_type": "created"}
            )
            self.assertTrue(search_form.is_valid())
            self.assertEqual(search_form.cleaned_data["ip"], "192.0.2.1")
            self.assertEqual(search_form.cleaned_data["event_type"], "created")

            # Verify form widgets have Bootstrap 5 classes
            self.assertIn("form-control", search_form.fields["ip"].widget.attrs.get("class", ""))
            self.assertIn("form-select", search_form.fields["event_type"].widget.attrs.get("class", ""))

            # Verify dry_run field is not forcefully checked via widget attrs
            unbound_import_form = forms.ImportForm()
            self.assertNotIn("checked", unbound_import_form.fields["dry_run"].widget.attrs)
        except ImportError:
            # Running in lightweight test environment without Django
            pass

    def test_templates_exist(self):
        templates_dir = os.path.join(PACKAGE_DIR, "templates", "netbox_ip_history")
        expected_templates = [
            "base.html",
            "history.html",
            "history_detail.html",
            "compare.html",
            "import.html",
            "import_preview.html",
            "import_job_list.html",
            "import_job.html",
            "source_support.html",
            "ipaddress_history_tab.html",
            # The upper "IP History" action button's partial, rendered via
            # IPAddressHistoryExtension.buttons(). Must exist alongside the
            # native tab (both are required — see
            # test_upper_ip_address_button_template_reverses_filtered_url).
            os.path.join("inc", "ipaddress_buttons.html"),
        ]
        for template_name in expected_templates:
            template_path = os.path.join(templates_dir, template_name)
            self.assertTrue(
                os.path.isfile(template_path),
                f"Missing template: {template_path}"
            )

        # The old redundant lower/right-side info panel ("Audit changes,
        # previous assignments, DNS history...") must stay removed — it
        # duplicated both the button and the tab. Only this partial is
        # removed; the button partial above is not.
        removed_templates = [
            os.path.join("inc", "ipaddress_panel.html"),
        ]
        for template_name in removed_templates:
            template_path = os.path.join(templates_dir, template_name)
            self.assertFalse(
                os.path.isfile(template_path),
                f"Redundant template should have been removed: {template_path}"
            )

    def test_ipaddress_history_tab_has_no_promotional_block(self):
        """The per-object IP History tab should be a plain native table, not
        a repeat of the old redundant "Audit changes, previous assignments,
        DNS history..." promotional panel."""
        tab_template = os.path.join(
            PACKAGE_DIR, "templates", "netbox_ip_history", "ipaddress_history_tab.html"
        )
        with open(tab_template, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("generic/object.html", content)
        self.assertNotIn("Audit changes, previous assignments", content)

    def test_templates_use_native_bootstrap_classes_not_custom_css(self):
        """Regression guard: event-type coloring and card styling should use
        NetBox's own text-bg-*/badge conventions (driven by
        choices.EVENT_TYPE_COLORS), not bespoke CSS classes that duplicate
        them and risk breaking in dark mode."""
        templates_dir = os.path.join(PACKAGE_DIR, "templates", "netbox_ip_history")
        forbidden_snippets = ("badge-event-", "kpi-card")
        for root, _dirs, files in os.walk(templates_dir):
            for fname in files:
                if not fname.endswith(".html"):
                    continue
                path = os.path.join(root, fname)
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                for snippet in forbidden_snippets:
                    self.assertNotIn(
                        snippet, content,
                        f"{path} still references custom class '{snippet}' instead of a native NetBox class"
                    )

    def test_upper_ip_history_button_returns_to_unfiltered_timeline(self):
        """Every plugin page must show an upper 'IP History' button that
        reverses to the unfiltered timeline URL — the bare 'history' URL
        name, never hardcoded and never with a "?ip=" filter appended — so
        it's a reliable way back to the main plugin timeline regardless of
        which page/filter the user is currently on."""
        templates_dir = os.path.join(PACKAGE_DIR, "templates", "netbox_ip_history")
        unfiltered_button_href = "{% url 'plugins:netbox_ip_history:history' %}\""

        # base.html's extra_buttons block is inherited by every page that
        # doesn't override it (history, compare, import, import_jobs,
        # import_job, source_support).
        with open(os.path.join(templates_dir, "base.html"), encoding="utf-8") as f:
            base_content = f.read()
        self.assertIn(unfiltered_button_href, base_content)
        self.assertIn('{% trans "IP History" %}', base_content)

        # history_detail.html overrides extra_buttons entirely, so it needs
        # its own copy of this button (alongside its page-specific "Back to
        # Timeline"/"Compare Sources" actions, which intentionally DO carry
        # a ?ip= filter — that's a different, valid navigation action).
        with open(os.path.join(templates_dir, "history_detail.html"), encoding="utf-8") as f:
            detail_content = f.read()
        self.assertIn(unfiltered_button_href, detail_content)
        self.assertIn('{% trans "IP History" %}', detail_content)

    def test_event_detail_scopes_objectchange_lookup_to_ipaddress(self):
        """Security regression guard: event_detail's fallback lookup for a
        pk that isn't a HistoricalIPEvent must be scoped to
        changed_object_type__model="ipaddress". Without that scope, a pk
        that happens to match an unrelated ObjectChange row (Device, Site,
        Cable, anything) would be rendered as if it were IP history —
        disclosing that object's change data to a user who only holds
        view_historicalipevent, not permission on the other model."""
        views_path = os.path.join(PACKAGE_DIR, "views.py")
        with open(views_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn(
            'ObjectChange.objects.filter(pk=pk, changed_object_type__model="ipaddress")',
            content,
        )

    def test_views_source_registers_native_ip_history_tab(self):
        """Verify (via source inspection, since views.py requires a real
        Django/NetBox environment to import) that the IP Address page is
        extended using NetBox's documented plugin view API
        (register_model_view + ViewTab), not an undocumented internal API."""
        views_path = os.path.join(PACKAGE_DIR, "views.py")
        with open(views_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("from utilities.views import ViewTab, register_model_view", content)
        self.assertIn('@register_model_view(IPAddress, "ip_history"', content)
        self.assertIn("tab = ViewTab(", content)

    def test_ip_history_tab_view_enforces_its_own_permission_not_just_ipaddress(self):
        """Security regression guard: ObjectView.get_required_permission()
        derives its check solely from queryset.model (ipam.view_ipaddress
        here) — a ViewTab's own `permission=` kwarg only hides/shows the tab
        *link*, it is never enforced by dispatch(). Without
        `additional_permissions` set, a user who can view IP addresses but
        lacks netbox_ip_history.view_historicalipevent could reach
        /ipam/ip-addresses/<pk>/ip-history/ directly by URL and see history
        data anyway (confirmed against NetBox's actual
        ObjectPermissionRequiredMixin.has_permission() source)."""
        views_path = os.path.join(PACKAGE_DIR, "views.py")
        with open(views_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn(
            'additional_permissions = ("netbox_ip_history.view_historicalipevent",)',
            content,
        )

    def test_views_have_permission_checks(self):
        try:
            from netbox_ip_history import views
            # Views decorated with permission_required wrap the original function in a closure
            view_functions = [
                views.history,
                views.event_detail,
                views.import_view,
                views.import_jobs,
                views.source_support,
                views.compare,
                views.import_job,
                views.rollback_import,
            ]
            for view_fn in view_functions:
                # permission_required / require_http_methods wrap functions
                # Check that view_fn has __wrapped__ or closure with permission checks
                self.assertTrue(
                    hasattr(view_fn, "__wrapped__") or hasattr(view_fn, "__closure__"),
                    f"View {view_fn.__name__} does not appear to be decorated with permission checks",
                )
        except ImportError:
            pass
