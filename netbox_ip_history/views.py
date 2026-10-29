import csv
import io
import json

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import View
from extras.ui.panels import CustomFieldsPanel, TagsPanel
from ipam.models import IPAddress
from netbox.object_actions import AddObject, BulkDelete, BulkEdit, BulkExport, DeleteObject, EditObject
from netbox.plugins import get_plugin_config
from netbox.ui import attrs, layout, panels
from netbox.views import generic
from utilities.query import count_related
from utilities.views import ContentTypePermissionRequiredMixin, ViewTab, register_model_view

from . import filtersets, forms, tables
from .choices import ImportStatusChoices
from .importers import support_matrix
from .jobs import ImportHistoryJobRunner
from .models import HistoricalIPEvent, ImportJob, ImportSource
from .services.import_service import build_importer, rollback_job, run_import
from .services.timeline import compare_sources, get_timeline

PLUGIN = "netbox_ip_history"


class PermissionRequiredView(ContentTypePermissionRequiredMixin, View):
    """Base for plugin workflow pages: default-closed, gated on a single model permission."""

    permission_required: str = ""

    def get_required_permission(self):
        return self.permission_required


#
# Panels
#

class ImportSourcePanel(panels.ObjectAttributesPanel):
    name = attrs.TextAttr("name")
    slug = attrs.TextAttr("slug", style="font-monospace")
    source_type = attrs.ChoiceAttr("source_type", label=_("Type"))
    enabled = attrs.BooleanAttr("enabled")
    source_timezone = attrs.TextAttr("source_timezone", label=_("Timezone"))
    source_priority = attrs.NumericAttr("source_priority", label=_("Priority"))
    description = attrs.TextAttr("description")


class ImportJobPanel(panels.ObjectAttributesPanel):
    source = attrs.RelatedObjectAttr("source", linkify=True)
    status = attrs.ChoiceAttr("status")
    import_mode = attrs.ChoiceAttr("import_mode", label=_("Mode"))
    user = attrs.TextAttr("user")
    started = attrs.DateTimeAttr("started")
    completed = attrs.DateTimeAttr("completed")
    filename = attrs.TextAttr("filename", style="font-monospace")
    file_size = attrs.NumericAttr("file_size", label=_("Size (bytes)"))
    file_hash = attrs.TextAttr("file_hash", label=_("SHA-256"), style="font-monospace", copy_button=True)


class ImportJobResultPanel(panels.ObjectAttributesPanel):
    total_records = attrs.NumericAttr("total_records", label=_("Records"))
    created_records = attrs.NumericAttr("created_records", label=_("Created"))
    duplicate_records = attrs.NumericAttr("duplicate_records", label=_("Duplicates"))
    error_records = attrs.NumericAttr("error_records", label=_("Errors"))


class HistoricalIPEventPanel(panels.ObjectAttributesPanel):
    timestamp = attrs.DateTimeAttr("timestamp")
    snapshot = attrs.BooleanAttr("snapshot", display_false=False)
    ip_address = attrs.TextAttr("ip_address", label=_("IP address"), style="font-monospace", copy_button=True)
    prefix_length = attrs.NumericAttr("prefix_length")
    scope = attrs.TextAttr("scope", label=_("VRF"))
    vrf_rd = attrs.TextAttr("vrf_rd", label=_("RD"))
    event_type = attrs.ChoiceAttr("event_type", label=_("Event"))
    source = attrs.RelatedObjectAttr("source", linkify=True)
    import_job = attrs.RelatedObjectAttr("import_job", linkify=True)
    source_username = attrs.TextAttr("source_username", label=_("User"))
    source_record_id = attrs.TextAttr("source_record_id", label=_("Source record"))
    related_netbox_ip = attrs.RelatedObjectAttr("related_netbox_ip", linkify=True, label=_("NetBox IP"))


class HistoricalIPEventOwnerPanel(panels.ObjectAttributesPanel):
    owner_name = attrs.TextAttr("owner_name", label=_("Owner"))
    owner_type = attrs.TextAttr("owner_type", label=_("Owner type"))
    hostname = attrs.TextAttr("hostname")
    dns_name = attrs.TextAttr("dns_name", label=_("DNS name"))
    interface_name = attrs.TextAttr("interface_name", label=_("Interface"))
    mac_address = attrs.TextAttr("mac_address", label=_("MAC address"), style="font-monospace")
    device_name = attrs.TextAttr("device_name", label=_("Device"))
    virtual_machine_name = attrs.TextAttr("virtual_machine_name", label=_("Virtual machine"))
    tenant_name = attrs.TextAttr("tenant_name", label=_("Tenant"))
    site = attrs.TextAttr("site")
    status = attrs.TextAttr("status")
    description = attrs.TextAttr("description")


#
# Import sources
#

@register_model_view(ImportSource, "list", path="", detail=False)
class ImportSourceListView(generic.ObjectListView):
    queryset = ImportSource.objects.annotate(
        job_count=count_related(ImportJob, "source"),
        event_count=count_related(HistoricalIPEvent, "source"),
    )
    table = tables.ImportSourceTable
    filterset = filtersets.ImportSourceFilterSet
    filterset_form = forms.ImportSourceFilterForm
    actions = (AddObject, BulkExport, BulkEdit, BulkDelete)


@register_model_view(ImportSource)
class ImportSourceView(generic.ObjectView):
    template_name = "generic/object.html"
    queryset = ImportSource.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[ImportSourcePanel(), TagsPanel()],
        right_panels=[panels.JSONPanel("field_mapping", title=_("Field mapping")), CustomFieldsPanel()],
        bottom_panels=[
            panels.ObjectsTablePanel(
                model="netbox_ip_history.ImportJob",
                title=_("Import jobs"),
                filters={"source_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


@register_model_view(ImportSource, "add", detail=False)
@register_model_view(ImportSource, "edit")
class ImportSourceEditView(generic.ObjectEditView):
    queryset = ImportSource.objects.all()
    form = forms.ImportSourceForm


@register_model_view(ImportSource, "delete")
class ImportSourceDeleteView(generic.ObjectDeleteView):
    queryset = ImportSource.objects.all()


@register_model_view(ImportSource, "bulk_edit", path="edit", detail=False)
class ImportSourceBulkEditView(generic.BulkEditView):
    queryset = ImportSource.objects.all()
    filterset = filtersets.ImportSourceFilterSet
    table = tables.ImportSourceTable
    form = forms.ImportSourceBulkEditForm


@register_model_view(ImportSource, "bulk_delete", path="delete", detail=False)
class ImportSourceBulkDeleteView(generic.BulkDeleteView):
    queryset = ImportSource.objects.all()
    filterset = filtersets.ImportSourceFilterSet
    table = tables.ImportSourceTable


#
# Import jobs
#

@register_model_view(ImportJob, "list", path="", detail=False)
class ImportJobListView(generic.ObjectListView):
    queryset = ImportJob.objects.select_related("source", "user")
    table = tables.ImportJobTable
    filterset = filtersets.ImportJobFilterSet
    filterset_form = forms.ImportJobFilterForm
    actions = (BulkExport, BulkDelete)


@register_model_view(ImportJob)
class ImportJobView(generic.ObjectView):
    template_name = "generic/object.html"
    queryset = ImportJob.objects.select_related("source", "user")
    actions = (EditObject, DeleteObject)
    layout = layout.SimpleLayout(
        left_panels=[ImportJobPanel(), TagsPanel()],
        right_panels=[
            ImportJobResultPanel(title=_("Result")),
            panels.TemplatePanel("netbox_ip_history/panels/rollback.html", title=_("Rollback")),
            panels.JSONPanel("error_details", title=_("Errors")),
        ],
        bottom_panels=[
            panels.ObjectsTablePanel(
                model="netbox_ip_history.HistoricalIPEvent",
                title=_("Events"),
                filters={"import_job_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


@register_model_view(ImportJob, "edit")
class ImportJobEditView(generic.ObjectEditView):
    """Only tags and custom fields are editable; job data is produced by the import."""

    queryset = ImportJob.objects.all()
    form = forms.ImportJobForm


@register_model_view(ImportJob, "delete")
class ImportJobDeleteView(generic.ObjectDeleteView):
    queryset = ImportJob.objects.all()


@register_model_view(ImportJob, "bulk_delete", path="delete", detail=False)
class ImportJobBulkDeleteView(generic.BulkDeleteView):
    queryset = ImportJob.objects.all()
    filterset = filtersets.ImportJobFilterSet
    table = tables.ImportJobTable


@register_model_view(ImportJob, "rollback")
class ImportJobRollbackView(PermissionRequiredView):
    permission_required = f"{PLUGIN}.delete_historicalipevent"

    def post(self, request, pk):
        job = get_object_or_404(ImportJob.objects.restrict(request.user, "change"), pk=pk)
        if job.status == ImportStatusChoices.ROLLED_BACK:
            messages.warning(request, _("Import job {job} was already rolled back.").format(job=job))
        else:
            deleted = rollback_job(job)
            messages.success(
                request, _("Rolled back import job {job}: {count} events deleted.").format(job=job, count=deleted)
            )
        return redirect(job.get_absolute_url())


#
# Historical IP events
#

@register_model_view(HistoricalIPEvent, "list", path="", detail=False)
class HistoricalIPEventListView(generic.ObjectListView):
    queryset = HistoricalIPEvent.objects.select_related("source", "import_job", "related_netbox_ip")
    table = tables.HistoricalIPEventTable
    filterset = filtersets.HistoricalIPEventFilterSet
    filterset_form = forms.HistoricalIPEventFilterForm
    actions = (BulkExport, BulkDelete)


@register_model_view(HistoricalIPEvent)
class HistoricalIPEventView(generic.ObjectView):
    template_name = "generic/object.html"
    queryset = HistoricalIPEvent.objects.select_related("source", "import_job", "related_netbox_ip")
    actions = (DeleteObject,)
    layout = layout.SimpleLayout(
        left_panels=[HistoricalIPEventPanel(), TagsPanel()],
        right_panels=[HistoricalIPEventOwnerPanel(title=_("Assignment")), CustomFieldsPanel()],
        bottom_panels=[panels.JSONPanel("raw_data", title=_("Source record"))],
    )


@register_model_view(HistoricalIPEvent, "delete")
class HistoricalIPEventDeleteView(generic.ObjectDeleteView):
    queryset = HistoricalIPEvent.objects.all()


@register_model_view(HistoricalIPEvent, "bulk_delete", path="delete", detail=False)
class HistoricalIPEventBulkDeleteView(generic.BulkDeleteView):
    queryset = HistoricalIPEvent.objects.all()
    filterset = filtersets.HistoricalIPEventFilterSet
    table = tables.HistoricalIPEventTable


#
# NetBox IP address tab
#

@register_model_view(IPAddress, "ip_history", path="ip-history")
class IPAddressHistoryView(generic.ObjectView):
    queryset = IPAddress.objects.all()
    # The tab permission only hides the link; additional_permissions enforces it on the URL too.
    additional_permissions = [f"{PLUGIN}.view_historicalipevent"]
    template_name = "netbox_ip_history/ipaddress_history.html"
    tab = ViewTab(label=_("IP History"), permission=f"{PLUGIN}.view_historicalipevent", weight=5000)

    def get_extra_context(self, request, instance):
        return {"events": get_timeline(str(instance.address.ip), user=request.user)}


#
# Workflows
#

_EXPORT_COLUMNS = (
    "timestamp", "ip_address", "vrf", "event_type", "source", "owner_name", "hostname", "dns_name",
    "interface_name", "mac_address", "status", "username", "description",
)


class TimelineView(PermissionRequiredView):
    permission_required = f"{PLUGIN}.view_historicalipevent"

    def get(self, request):
        form = forms.TimelineSearchForm(request.GET or None)
        events, ip = [], ""
        if form.is_valid() and form.cleaned_data["ip"]:
            ip = form.cleaned_data["ip"]
            events = get_timeline(**form.timeline_kwargs(), user=request.user)
            export = request.GET.get("export")
            if export in ("csv", "json"):
                return self._export(events, ip, export)
        return render(
            request,
            "netbox_ip_history/timeline.html",
            {
                "form": form,
                "ip": ip,
                "events": events,
                "sources": sorted({e["source"] for e in events}),
                "first_seen": min((e["timestamp"] for e in events), default=None),
                "last_seen": max((e["timestamp"] for e in events), default=None),
            },
        )

    @staticmethod
    def _export(events, ip, export_format):
        filename = f"ip-history-{ip.replace(':', '_')}-{timezone.now():%Y%m%d%H%M%S}.{export_format}"
        rows = [{key: event.get(key) for key in _EXPORT_COLUMNS} for event in events]
        if export_format == "json":
            response = HttpResponse(
                json.dumps(rows, cls=DjangoJSONEncoder, indent=2), content_type="application/json"
            )
        else:
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=_EXPORT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
            response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class CompareView(PermissionRequiredView):
    permission_required = f"{PLUGIN}.view_historicalipevent"

    def get(self, request):
        form = forms.CompareForm(request.GET or None)
        rows, ip = [], ""
        if form.is_valid() and form.cleaned_data["ip"]:
            ip = form.cleaned_data["ip"]
            rows = compare_sources(ip, user=request.user)
        return render(request, "netbox_ip_history/compare.html", {"form": form, "ip": ip, "rows": rows})


class SourceSupportView(PermissionRequiredView):
    permission_required = f"{PLUGIN}.view_importsource"

    def get(self, request):
        return render(request, "netbox_ip_history/source_support.html", {"matrix": support_matrix()})


class ImportView(PermissionRequiredView):
    permission_required = f"{PLUGIN}.add_historicalipevent"
    additional_permissions = [f"{PLUGIN}.add_importjob"]
    template_name = "netbox_ip_history/import.html"

    def get(self, request):
        return render(request, self.template_name, {"form": forms.ImportForm(user=request.user)})

    def post(self, request):
        form = forms.ImportForm(request.POST, request.FILES, user=request.user)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        source = form.cleaned_data["source"]
        upload = form.cleaned_data["file"]
        data = upload.read()
        fmt, delimiter = form.cleaned_data["format"], form.cleaned_data["delimiter"] or ","
        dry_run = form.cleaned_data["dry_run"]

        threshold = get_plugin_config(PLUGIN, "background_import_threshold")
        if not dry_run and (form.cleaned_data["background"] or len(data) >= threshold):
            job = ImportJob.objects.create(
                source=source, user=request.user, filename=upload.name[:255], file_size=len(data),
                status=ImportStatusChoices.PENDING,
            )
            ImportHistoryJobRunner.enqueue(
                instance=job, user=request.user, data=data, format=fmt, delimiter=delimiter
            )
            messages.info(request, _("Import queued as a background job."))
            return redirect(job.get_absolute_url())

        importer = build_importer(source, data, format=fmt, delimiter=delimiter)
        try:
            result, job = run_import(
                source, importer, dry_run=dry_run, user=request.user, filename=upload.name, data=data
            )
        except Exception as exc:
            form.add_error(None, _("Import failed: {error}").format(error=exc))
            return render(request, self.template_name, {"form": form})

        for warning in result.warnings:
            messages.warning(request, warning)
        if job is not None:
            messages.success(
                request,
                _("Imported {created} of {total} records.").format(created=result.created, total=result.total),
            )
            return redirect(job.get_absolute_url())
        return render(
            request,
            self.template_name,
            {"form": form, "result": result, "source": source, "filename": upload.name},
        )
