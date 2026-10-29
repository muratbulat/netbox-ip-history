from datetime import date

from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from netbox.api.authentication import IsAuthenticatedOrLoginNotRequired
from netbox.api.viewsets import NetBoxModelViewSet
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import filtersets
from ..models import HistoricalIPEvent, ImportJob, ImportSource
from ..services.normalize import RecordError, normalize_ip
from ..services.timeline import compare_sources, get_timeline
from .serializers import (
    CompareRowSerializer,
    HistoricalIPEventSerializer,
    ImportJobSerializer,
    ImportSourceSerializer,
    TimelineEntrySerializer,
)

VIEW_PERMISSION = "netbox_ip_history.view_historicalipevent"
_IP_PARAMETER = OpenApiParameter("ip", OpenApiTypes.STR, required=True, description="IPv4 or IPv6 address")


class ImportSourceViewSet(NetBoxModelViewSet):
    queryset = ImportSource.objects.all()
    serializer_class = ImportSourceSerializer
    filterset_class = filtersets.ImportSourceFilterSet


class ImportJobViewSet(NetBoxModelViewSet):
    """Jobs are created by imports; the API can read, tag and delete them."""

    queryset = ImportJob.objects.select_related("source", "user").prefetch_related("tags")
    serializer_class = ImportJobSerializer
    filterset_class = filtersets.ImportJobFilterSet
    http_method_names = ["get", "patch", "delete", "head", "options"]


class HistoricalIPEventViewSet(NetBoxModelViewSet):
    """Events are immutable facts; the API can read, tag and delete them."""

    queryset = HistoricalIPEvent.objects.select_related(
        "source", "import_job", "related_netbox_ip"
    ).prefetch_related("tags")
    serializer_class = HistoricalIPEventSerializer
    filterset_class = filtersets.HistoricalIPEventFilterSet
    http_method_names = ["get", "patch", "delete", "head", "options"]


class _IPQueryView(APIView):
    permission_classes = [IsAuthenticatedOrLoginNotRequired]

    def get_ip(self, request) -> str:
        if not request.user.has_perm(VIEW_PERMISSION):
            raise PermissionDenied()
        try:
            return normalize_ip(request.query_params.get("ip", ""))[0]
        except RecordError as exc:
            raise ValidationError({"ip": _("A valid IPv4 or IPv6 address is required.")}) from exc


def _date_param(params, name):
    value = params.get(name, "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({name: _("Use the YYYY-MM-DD date format.")}) from exc


class TimelineView(_IPQueryView):
    """Merged native and imported history for one IP address, newest first."""

    @extend_schema(
        parameters=[
            _IP_PARAMETER,
            OpenApiParameter("vrf", OpenApiTypes.STR, description="VRF name/RD, or 'Global'"),
            OpenApiParameter("source", OpenApiTypes.STR),
            OpenApiParameter("event_type", OpenApiTypes.STR),
            OpenApiParameter("date_from", OpenApiTypes.DATE, description="Events on or after this date (YYYY-MM-DD)"),
            OpenApiParameter("date_to", OpenApiTypes.DATE, description="Events on or before this date (YYYY-MM-DD)"),
            OpenApiParameter("owner", OpenApiTypes.STR, description="Owner, hostname, device or VM name contains"),
            OpenApiParameter("username", OpenApiTypes.STR, description="Acting/source user name contains"),
            OpenApiParameter("oldest_first", OpenApiTypes.BOOL),
        ],
        responses={200: TimelineEntrySerializer(many=True)},
    )
    def get(self, request):
        ip = self.get_ip(request)
        params = request.query_params
        entries = get_timeline(
            ip,
            vrf=params.get("vrf", ""),
            source=params.get("source", ""),
            event_type=params.get("event_type", ""),
            date_from=_date_param(params, "date_from"),
            date_to=_date_param(params, "date_to"),
            owner=params.get("owner", ""),
            username=params.get("username", ""),
            oldest_first=params.get("oldest_first", "").lower() in ("1", "true", "yes"),
            user=request.user,
        )
        return Response(TimelineEntrySerializer(entries, many=True).data)


class CompareView(_IPQueryView):
    """Latest state of one IP address according to each source."""

    @extend_schema(parameters=[_IP_PARAMETER], responses={200: CompareRowSerializer(many=True)})
    def get(self, request):
        rows = compare_sources(self.get_ip(request), user=request.user)
        return Response(CompareRowSerializer(rows, many=True).data)
