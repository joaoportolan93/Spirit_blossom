"""
URLs raiz — M0: apenas health check.
Apps de domínio incluídos em M1a.
"""

from django.contrib import admin
from django.urls import include, path

from .views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health"),
    # M1a: include("accounts.urls"), include("posts.urls"), etc.
]

