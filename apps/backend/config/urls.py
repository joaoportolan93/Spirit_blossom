"""
URLs raiz — Consolidadas no app core (estilo Lumem).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .views import ProtectedMediaView, health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health"),
    path("api/media/<path:file_path>", ProtectedMediaView.as_view(), name="protected_media"),
    path("api/", include("core.urls")),
    path("api/", include("comments.urls")),
]

if settings.DEBUG and not settings.MEDIA_URL.startswith("/protected-media"):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
