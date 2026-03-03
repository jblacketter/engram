from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from engram.views import FrontendView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # SPA catch-all: serves index.html for all non-API/admin/static routes
    re_path(r"^(?!(api|admin|static)(/|$)).*$", FrontendView.as_view(), name="frontend"),
]
