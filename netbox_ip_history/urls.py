from django.urls import path

from . import views

urlpatterns = [
    path("", views.history, name="history"),
    path("event/<str:pk>/", views.event_detail, name="event"),
    path("import/", views.import_view, name="import"),
    path("import-jobs/", views.import_jobs, name="import_jobs"),
    path("sources/support/", views.source_support, name="source_support"),
    path("compare/", views.compare, name="compare"),
    path("import-jobs/<int:pk>/", views.import_job, name="import_job"),
    path("import-jobs/<int:pk>/rollback/", views.rollback_import, name="rollback_import"),
]