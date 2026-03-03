from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("memories/", views.MemoryListCreateView.as_view(), name="memory-list"),
    path(
        "memories/<uuid:pk>/", views.MemoryDetailView.as_view(), name="memory-detail"
    ),
    path("search/", views.SearchView.as_view(), name="search"),
    path("stats/", views.StatsView.as_view(), name="stats"),
    path("tags/", views.TagsView.as_view(), name="tags"),
    # Ingestion
    path("ingest/file/", views.IngestFileView.as_view(), name="ingest-file"),
    path("ingest/url/", views.IngestURLView.as_view(), name="ingest-url"),
    path("ingest/batch/", views.IngestBatchView.as_view(), name="ingest-batch"),
]
