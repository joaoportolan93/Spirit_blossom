from rest_framework import permissions


class IsAdminPermission(permissions.BasePermission):
    """Permite acesso apenas a administradores autenticados (is_staff ou is_superuser)."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )
