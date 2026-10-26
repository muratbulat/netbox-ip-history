from django.urls import include, path
from utilities.urls import get_model_urls

from . import views

app_name = "netbox_ip_history"

urlpatterns = [
    path("", views.TimelineView.as_view(), name="timeline"),
    path("compare/", views.CompareView.as_view(), name="compare"),
    path("import/", views.ImportView.as_view(), name="import"),
    path("supported-formats/", views.SourceSupportView.as_view(), name="source_support"),
    path("sources/", include(get_model_urls(app_name, "importsource", detail=False))),
    path("sources/<int:pk>/", include(get_model_urls(app_name, "importsource"))),
    path("import-jobs/", include(get_model_urls(app_name, "importjob", detail=False))),
    path("import-jobs/<int:pk>/", include(get_model_urls(app_name, "importjob"))),
    path("events/", include(get_model_urls(app_name, "historicalipevent", detail=False))),
    path("events/<int:pk>/", include(get_model_urls(app_name, "historicalipevent"))),
]
