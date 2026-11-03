"""
URLs raiz — M1a: todos os apps de domínio incluídos.
"""

from django.contrib import admin
from django.urls import include, path

from .views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health"),
    path("api/auth/", include("accounts.urls", namespace="accounts")),
    path("api/posts/", include("posts.urls", namespace="posts")),
    path("api/social/", include("social.urls", namespace="social")),
    path("api/feed/", include("feed.urls", namespace="feed")),
    path("api/notifications/", include("notifications.urls", namespace="notifications")),
]
