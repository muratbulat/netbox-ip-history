from django.urls import path
from netbox.api.routers import NetBoxRouter

from . import views

router = NetBoxRouter()
router.register("sources", views.ImportSourceViewSet)
router.register("import-jobs", views.ImportJobViewSet)
router.register("events", views.HistoricalIPEventViewSet)

urlpatterns = [
    path("timeline/", views.TimelineView.as_view(), name="timeline"),
    path("compare/", views.CompareView.as_view(), name="compare"),
    *router.urls,
]
