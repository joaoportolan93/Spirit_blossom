"""
Views administrativas divididas por subdomínio (Onda 8 / padrão Lumem).
"""

from core.views.reports import CreateReportView

from .feature_flags import AdminFeatureFlagDetailView, AdminFeatureFlagListView
from .permissions import IsAdminPermission
from .reports import AdminModerationLogsView, AdminReportActionView, AdminReportsView
from .stats import AdminStatsView
from .users import AdminUserDetailView, AdminUsersView

__all__ = [
    "AdminFeatureFlagDetailView",
    "AdminFeatureFlagListView",
    "AdminModerationLogsView",
    "AdminReportActionView",
    "AdminReportsView",
    "AdminStatsView",
    "AdminUserDetailView",
    "AdminUsersView",
    "CreateReportView",
    "IsAdminPermission",
]
