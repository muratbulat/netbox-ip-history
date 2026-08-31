import csv
import hashlib
import io
import logging

from django.contrib.auth.decorators import permission_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .choices import EVENT_TYPE_COLORS
from .forms import HistorySearchForm, ImportForm
from .importers import GenericCSVImporter, importer_for, support_matrix
from .models import HistoricalIPEvent, ImportJob
from .services.import_service import rollback_job, run_import
from .services.timeline import NativeEventWrapper, get_timeline, native_events

from ipam.models import IPAddress
from netbox.views.generic import ObjectView
from utilities.views import ViewTab, register_model_view

try:
    from django.utils.translation import gettext_lazy as _
except ImportError:
    _ = lambda s: s


@permission_required("netbox_ip_history.view_historicalipevent", raise_exception=True)
def event_detail(request, pk):
    is_native = request.GET.get("native") == "1"
    event = None

    if not is_native:
        try:
            event = HistoricalIPEvent.objects.filter(pk=pk).select_related("source", "import_job").first()
        except (ValueError, TypeError):
            event = None

    if not event:
        try:
            from core.models import ObjectChange
            # Scoped to changed_object_type__model="ipaddress": without this,
            # a HistoricalIPEvent pk that doesn't exist (e.g. a rolled-back
            # or never-synced event) would fall through to look up *any*
            # ObjectChange row by that same pk — including changes to
            # unrelated models (Device, Site, Cable, ...) that a user with
            # only view_historicalipevent has no permission to view
            # directly. Scoping here prevents that cross-model disclosure.
            change = ObjectChange.objects.filter(pk=pk, changed_object_type__model="ipaddress").first()
            if change:
                event = NativeEventWrapper(change, ip_address=request.GET.get("ip"))
        except (ImportError, ValueError, TypeError):
            pass

    if not event and is_native:
        try:
            event = HistoricalIPEvent.objects.filter(pk=pk).select_related("source", "import_job").first()
        except (ValueError, TypeError):
            event = None

    if not event:
        raise Http404("Event not found")

    event.color = EVENT_TYPE_COLORS.get(event.event_type, "secondary")

    return render(
        request,
        "netbox_ip_history/history_detail.html",
        {"event": event, "active_tab": "history"},
    )

logger = logging.getLogger("netbox.plugins.netbox_ip_history")
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB limit for web uploads


@register_model_view(IPAddress, "ip_history", path="ip-history")
class IPAddressHistoryTabView(ObjectView):
    """
    Registers a native "IP History" tab on NetBox's own IP Address detail
    page (alongside its built-in "Changelog"/"Journal" tabs), per NetBox's
    documented plugin view API (utilities.views.register_model_view +
    ViewTab). This is the sole integration point into the IP Address page —
    intentionally no separate button or info panel duplicates it.
    """
    queryset = IPAddress.objects.all()
    tab = ViewTab(label=_("IP History"), permission="netbox_ip_history.view_historicalipevent")
    template_name = "netbox_ip_history/ipaddress_history_tab.html"

    # ObjectView.get_required_permission() derives its permission solely
    # from `queryset.model` (ipam.view_ipaddress here) — the tab's own
    # `permission` above only controls whether the tab *link* is shown, it
    # is never enforced by dispatch(). Without this, a user who can view IP
    # addresses but lacks netbox_ip_history.view_historicalipevent could
    # still reach this page directly by URL and see history data. This is
    # ObjectPermissionRequiredMixin's documented extension point for
    # exactly that: has_permission() requires ALL of these, in addition to
    # the auto-derived ipam.view_ipaddress.
    additional_permissions = ("netbox_ip_history.view_historicalipevent",)

    def get_extra_context(self, request, instance):
        events = get_timeline(str(instance.address.ip))
        for event in events:
            event["color"] = EVENT_TYPE_COLORS.get(event["event_type"], "secondary")
        return {
            "events": events,
            "full_timeline_url": f"{reverse('plugins:netbox_ip_history:history')}?ip={instance.address.ip}",
        }


@permission_required("netbox_ip_history.view_historicalipevent", raise_exception=True)
def history(request):
    form = HistorySearchForm(request.GET or None)
    events = []
    ip = ""
    stats = {}
    if form.is_valid():
        ip = form.cleaned_data.get("ip") or ""
        if ip:
            events = get_timeline(
                ip_address=ip,
                vrf=form.cleaned_data.get("vrf", ""),
                source=form.cleaned_data.get("source", ""),
                event_type=form.cleaned_data.get("event_type", ""),
                oldest_first=form.cleaned_data.get("oldest_first", False),
                date_from=form.cleaned_data.get("date_from"),
                date_to=form.cleaned_data.get("date_to"),
                owner=form.cleaned_data.get("owner", ""),
                username=form.cleaned_data.get("username", ""),
            )
            for event in events:
                event["color"] = EVENT_TYPE_COLORS.get(event["event_type"], "secondary")
            if events:
                distinct_sources = set(e.get("source") for e in events if e.get("source"))
                stats = {
                    "total_events": len(events),
                    "sources_count": len(distinct_sources),
                    "sources": list(distinct_sources),
                    "first_seen": events[-1]["timestamp"] if not form.cleaned_data.get("oldest_first") else events[0]["timestamp"],
                    "last_seen": events[0]["timestamp"] if not form.cleaned_data.get("oldest_first") else events[-1]["timestamp"],
                }

    export_format = request.GET.get("export", "").lower()
    if export_format in ("csv", "json") and events:
        filename_prefix = f"ip_history_{ip or 'all'}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        if export_format == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{filename_prefix}.csv"'
            writer = csv.writer(response)
            writer.writerow([
                "Timestamp", "IP Address", "Event Type", "Source", "VRF / Scope",
                "Owner / Host", "DNS Name", "Interface", "Username", "Description"
            ])
            for e in events:
                writer.writerow([
                    str(e.get("timestamp") or ""),
                    e.get("ip_address") or "",
                    e.get("event_type") or "",
                    e.get("source") or "",
                    e.get("vrf") or "",
                    e.get("owner_name") or "",
                    e.get("dns_name") or "",
                    e.get("interface_name") or "",
                    e.get("username") or "",
                    e.get("description") or "",
                ])
            return response
        elif export_format == "json":
            serializable_events = []
            for e in events:
                item = dict(e)
                if "timestamp" in item and hasattr(item["timestamp"], "isoformat"):
                    item["timestamp"] = item["timestamp"].isoformat()
                if "raw_reference" in item:
                    del item["raw_reference"]
                serializable_events.append(item)
            response = JsonResponse(serializable_events, safe=False, json_dumps_params={"indent": 2})
            response["Content-Disposition"] = f'attachment; filename="{filename_prefix}.json"'
            return response

    show_filters_tab = request.GET.get("tab") == "filters"
    return render(
        request,
        "netbox_ip_history/history.html",
        {
            "form": form,
            "events": events,
            "ip": ip,
            "stats": stats,
            "active_tab": "history",
            "show_filters_tab": show_filters_tab,
        },
    )




@permission_required("netbox_ip_history.add_historicalipevent", raise_exception=True)
@require_http_methods(["GET", "POST"])
def import_view(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        upload = form.cleaned_data["file"]
        if upload.size > MAX_UPLOAD_SIZE:
            form.add_error("file", f"File size ({upload.size / (1024*1024):.1f} MB) exceeds maximum allowed limit (50 MB).")
            return render(request, "netbox_ip_history/import.html", {"form": form, "active_tab": "import"})

        data = upload.read()
        is_dry_run = bool(form.cleaned_data.get("dry_run"))
        job = ImportJob.objects.create(
            source=form.cleaned_data["source"],
            user=request.user,
            filename=upload.name,
            file_hash=hashlib.sha256(data).hexdigest(),
            file_size=len(data),
            dry_run=is_dry_run,
        )
        importer_class = importer_for(job.source.source_type) or GenericCSVImporter
        stream = io.BytesIO(data)
        try:
            importer = importer_class(job.source, stream, format=form.cleaned_data["format"])
        except TypeError:
            if form.cleaned_data["format"] == "csv":
                try:
                    importer = importer_class(job.source, stream, delimiter=form.cleaned_data["delimiter"])
                except TypeError:
                    importer = importer_class(job.source, stream)
            else:
                importer = importer_class(job.source, stream)
        job.import_mode = "history_only"
        job.dry_run = is_dry_run
        job.save(update_fields=["import_mode", "dry_run"])
        job = run_import(job, importer, dry_run=is_dry_run)
        return render(
            request,
            "netbox_ip_history/import_preview.html",
            {"job": job, "dry_run": is_dry_run, "active_tab": "import"},
        )
    return render(
        request,
        "netbox_ip_history/import.html",
        {"form": form, "active_tab": "import"},
    )


@permission_required("netbox_ip_history.view_importjob", raise_exception=True)
def import_jobs(request):
    return render(
        request,
        "netbox_ip_history/import_job_list.html",
        {"jobs": ImportJob.objects.select_related("source", "user"), "active_tab": "import_jobs"},
    )


@permission_required("netbox_ip_history.view_importsource", raise_exception=True)
def source_support(request):
    return render(
        request,
        "netbox_ip_history/source_support.html",
        {"matrix": support_matrix(), "active_tab": "source_support"},
    )


@permission_required("netbox_ip_history.view_historicalipevent", raise_exception=True)
def compare(request):
    form = HistorySearchForm(request.GET or None)
    rows, ip = [], ""
    if form.is_valid():
        ip = form.cleaned_data.get("ip") or ""
        if ip:
            seen_sources = set()
            for event in HistoricalIPEvent.objects.filter(ip_address=ip).select_related("source").order_by("source__name", "-timestamp"):
                if event.source.name not in seen_sources:
                    seen_sources.add(event.source.name)
                    rows.append({
                        "source": event.source.name,
                        "hostname": event.hostname or "-",
                        "owner": event.owner_name or event.device_name or event.virtual_machine_name or "-",
                        "dns": event.dns_name or "-",
                        "mac": event.mac_address or "-",
                        "vrf": event.vrf_name or event.vrf_rd or "Global",
                        "last_seen": event.timestamp,
                        "native": False,
                    })
            native_items = native_events(ip)
            if native_items:
                latest_native = native_items[0]
                rows.insert(0, {
                    "source": "NetBox",
                    "hostname": latest_native.get("hostname") or "-",
                    "owner": latest_native.get("owner_name") or "-",
                    "dns": latest_native.get("dns_name") or "-",
                    "mac": "-",
                    "vrf": latest_native.get("vrf") or "Global",
                    "last_seen": latest_native.get("timestamp"),
                    "native": True,
                })
            try:
                from django.apps import apps
                if apps.is_installed("netbox_ping"):
                    from netbox_ping.models import PingResult
                    from django.db.models import Q
                    pr = PingResult.objects.filter(
                        Q(ip_address__address__startswith=f"{ip}/") | Q(ip_address__address=ip)
                    ).select_related("ip_address", "ip_address__vrf").first()
                    if pr:
                        status_str = f"ICMP Up (RTT: {pr.response_time_ms}ms)" if pr.is_reachable else "ICMP Down / Unreachable"
                        rows.append({
                            "source": "NetBox Ping",
                            "hostname": pr.dns_name or "-",
                            "owner": status_str,
                            "dns": pr.dns_name or "-",
                            "mac": "-",
                            "vrf": getattr(getattr(pr.ip_address, "vrf", None), "name", "Global") or "Global",
                            "last_seen": pr.last_seen or pr.discovered_at or pr.last_checked,
                            "native": False,
                        })
            except Exception:
                pass
    return render(
        request,
        "netbox_ip_history/compare.html",
        {"form": form, "rows": rows, "ip": ip, "active_tab": "compare"},
    )


@permission_required("netbox_ip_history.view_importjob", raise_exception=True)
def import_job(request, pk):
    return render(
        request,
        "netbox_ip_history/import_job.html",
        {"job": get_object_or_404(ImportJob.objects.select_related("source", "user"), pk=pk), "active_tab": "import_jobs"},
    )


@permission_required("netbox_ip_history.delete_historicalipevent", raise_exception=True)
@require_http_methods(["POST"])
def rollback_import(request, pk):
    job = get_object_or_404(ImportJob, pk=pk)
    if request.POST.get("confirm") == "yes":
        rollback_job(job)
    return render(
        request,
        "netbox_ip_history/import_job.html",
        {"job": job, "rolled_back": True, "active_tab": "import_jobs"},
    )