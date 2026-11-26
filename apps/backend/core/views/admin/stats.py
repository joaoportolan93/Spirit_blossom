from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Report
from core.services.posts import get_admin_post_stats
from core.views.admin.permissions import IsAdminPermission

User = get_user_model()


class AdminStatsView(APIView):
    """GET /api/admin/stats/ — KPIs e série histórica dos últimos 7 dias."""

    permission_classes = [IsAdminPermission]

    def get(self, request):
        now = timezone.now()
        today = now.date()
        seven_days_ago = today - timedelta(days=6)

        total_users = User.objects.count()
        banned_users = User.objects.filter(status=User.Status.SUSPENDED).count()
        post_stats = get_admin_post_stats(today, seven_days_ago)
        total_posts = post_stats["total_posts"]
        hidden_posts = post_stats["hidden_posts"]
        pending_reports = Report.objects.filter(status=Report.Status.PENDING).count()
        total_reports = Report.objects.count()
        new_users_today = User.objects.filter(date_joined__date=today).count()
        new_posts_today = post_stats["new_posts_today"]

        signups_by_day = dict(
            User.objects.filter(date_joined__date__gte=seven_days_ago)
            .annotate(day=TruncDate("date_joined"))
            .values("day")
            .annotate(total=Count("id"))
            .values_list("day", "total")
        )
        reports_by_day = dict(
            Report.objects.filter(created_at__date__gte=seven_days_ago)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"))
            .values_list("day", "total")
        )
        posts_by_day = post_stats["posts_by_day"]

        daily_stats = []
        for i in range(7):
            day = today - timedelta(days=6 - i)
            daily_stats.append(
                {
                    "date": day.isoformat(),
                    "signups": signups_by_day.get(day, 0),
                    "reports": reports_by_day.get(day, 0),
                    "posts": posts_by_day.get(day, 0),
                }
            )

        return Response(
            {
                "kpis": {
                    "total_users": total_users,
                    "banned_users": banned_users,
                    "total_posts": total_posts,
                    "hidden_posts": hidden_posts,
                    "pending_reports": pending_reports,
                    "total_reports": total_reports,
                    "new_users_today": new_users_today,
                    "new_posts_today": new_posts_today,
                },
                "daily_stats": daily_stats,
            }
        )
