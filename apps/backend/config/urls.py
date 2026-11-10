"""
URLs raiz — Consolidadas no app core (estilo Lumem).
"""

from django.contrib import admin
from django.urls import include, path

from .views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health"),
    path("api/", include("core.urls")),
    path("api/", include("comments.urls")),
]
