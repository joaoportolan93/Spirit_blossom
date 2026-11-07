"""
URLs de usuários (busca, perfil público). Montado em /api/users/.
"""

from django.urls import path

from .views import UserSearchView

app_name = "users"

urlpatterns = [
    path("search/", UserSearchView.as_view(), name="search"),
]

