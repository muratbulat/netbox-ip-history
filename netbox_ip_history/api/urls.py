try:
    from netbox.api.routers import NetBoxRouter
    router = NetBoxRouter()
except ImportError:
    try:
        from rest_framework.routers import DefaultRouter
        router = DefaultRouter()
    except ImportError:
        router = None

if router:
    from .views import (
        HistoricalIPEventViewSet,
        ImportJobViewSet,
        ImportSourceViewSet,
    )

    router.register("sources", ImportSourceViewSet)
    router.register("jobs", ImportJobViewSet)
    router.register("events", HistoricalIPEventViewSet)
    urlpatterns = router.urls
else:
    urlpatterns = []
