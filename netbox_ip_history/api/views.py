try:
    from netbox.api.viewsets import NetBoxModelViewSet
    ModelViewSetClass = NetBoxModelViewSet
except ImportError:
    try:
        from rest_framework.viewsets import ModelViewSet
        ModelViewSetClass = ModelViewSet
    except ImportError:
        class ModelViewSetClass:
            pass

from ..filtersets import (
    HistoricalIPEventFilterSet,
    ImportJobFilterSet,
    ImportSourceFilterSet,
)
from ..models import HistoricalIPEvent, ImportJob, ImportSource
from .serializers import (
    HistoricalIPEventSerializer,
    ImportJobSerializer,
    ImportSourceSerializer,
)


class ImportSourceViewSet(ModelViewSetClass):
    queryset = ImportSource.objects.all() if hasattr(ImportSource, "objects") else None
    serializer_class = ImportSourceSerializer
    filterset_class = ImportSourceFilterSet


class ImportJobViewSet(ModelViewSetClass):
    queryset = ImportJob.objects.select_related("source", "user").all() if hasattr(ImportJob, "objects") else None
    serializer_class = ImportJobSerializer
    filterset_class = ImportJobFilterSet


class HistoricalIPEventViewSet(ModelViewSetClass):
    queryset = HistoricalIPEvent.objects.select_related("source", "import_job").all() if hasattr(HistoricalIPEvent, "objects") else None
    serializer_class = HistoricalIPEventSerializer
    filterset_class = HistoricalIPEventFilterSet
