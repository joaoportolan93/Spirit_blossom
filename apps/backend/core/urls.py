"""
URLs agregadas do app core (estilo Lumem).
Preserva todas as rotas públicas, caminhos e namespaces.
"""

from django.urls import include, path

from core.views.admin import (
    AdminFeatureFlagDetailView,
    AdminFeatureFlagListView,
    AdminModerationLogsView,
    AdminReportActionView,
    AdminReportsView,
    AdminStatsView,
    AdminUserDetailView,
    AdminUsersView,
)
from core.views.auth import (
    ChangePasswordView,
    CSRFView,
    CurrentUserView,
    DeleteAccountView,
    GoogleAuthView,
    GoogleCompleteSignupView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    TokenRefreshView,
    UserDataExportView,
    UserSearchView,
    UserSettingsView,
)
from core.views.feature_flags import FeatureFlagsView
from core.views.feed import ExploreFeedView, FollowingFeedView
from core.views.notifications import (
    NotificationListView,
    NotificationMarkReadView,
    NotificationUnreadCountView,
    PushDeviceView,
)
from core.views.posts import (
    BookmarkedPostListView,
    DraftDetailView,
    DraftListCreateView,
    DraftPublishView,
    PostBookmarkView,
    PostDetailView,
    PostLikeView,
    PostListCreateView,
    PostSearchView,
    TrendingHashtagsView,
)
from core.views.reports import CreateReportView
from core.views.social import (
    BlockedUsersListView,
    BlockView,
    CloseFriendsCandidatesView,
    CloseFriendsListView,
    CloseFriendsView,
    FollowRequestAcceptView,
    FollowRequestListView,
    FollowRequestRejectView,
    FollowSuggestionsView,
    FollowView,
    MutedUsersListView,
    MuteView,
    ProfileDetailView,
    ProfileLikesView,
)

auth_patterns = [
    path("csrf/", CSRFView.as_view(), name="csrf"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current_user"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("google/", GoogleAuthView.as_view(), name="google_auth"),
    path("google/complete/", GoogleCompleteSignupView.as_view(), name="google_complete"),
]

users_patterns = [
    path("profile/", UserSettingsView.as_view(), name="profile_update"),
    path("settings/", UserSettingsView.as_view(), name="user_settings"),
    path("search/", UserSearchView.as_view(), name="search"),
    path("export-data/", UserDataExportView.as_view(), name="export_data"),
    path("account/", DeleteAccountView.as_view(), name="delete_account"),
]

posts_patterns = [
    path("", PostListCreateView.as_view(), name="post_list_create"),
    path("search/", PostSearchView.as_view(), name="post_search"),
    path("bookmarks/", BookmarkedPostListView.as_view(), name="post_bookmarks"),
    path("drafts/", DraftListCreateView.as_view(), name="draft_list_create"),
    path("drafts/<uuid:pk>/", DraftDetailView.as_view(), name="draft_detail"),
    path("drafts/<uuid:pk>/publish/", DraftPublishView.as_view(), name="draft_publish"),
    path("<uuid:pk>/", PostDetailView.as_view(), name="post_detail"),
    path("<uuid:pk>/like/", PostLikeView.as_view(), name="post_like"),
    path("<uuid:pk>/bookmark/", PostBookmarkView.as_view(), name="post_bookmark"),
]

social_patterns = [
    path("follow/<str:username>/", FollowView.as_view(), name="follow"),
    path("follow-requests/", FollowRequestListView.as_view(), name="follow_requests_list"),
    path(
        "follow-requests/<str:username>/accept/",
        FollowRequestAcceptView.as_view(),
        name="follow_request_accept",
    ),
    path(
        "follow-requests/<str:username>/reject/",
        FollowRequestRejectView.as_view(),
        name="follow_request_reject",
    ),
    path("block/<str:username>/", BlockView.as_view(), name="block"),
    path("blocked-users/", BlockedUsersListView.as_view(), name="blocked_users_list"),
    path("mute/<str:username>/", MuteView.as_view(), name="mute"),
    path("muted-users/", MutedUsersListView.as_view(), name="muted_users_list"),
    path("close-friends/", CloseFriendsListView.as_view(), name="close-friends-list"),
    path(
        "close-friends/candidates/",
        CloseFriendsCandidatesView.as_view(),
        name="close-friends-candidates",
    ),
    path("close-friends/<str:username>/", CloseFriendsView.as_view(), name="close-friends"),
    path("profile/<str:username>/", ProfileDetailView.as_view(), name="profile"),
    path("profile/<str:username>/likes/", ProfileLikesView.as_view(), name="profile_likes"),
    path("suggestions/", FollowSuggestionsView.as_view(), name="follow_suggestions"),
]

hashtags_patterns = [
    path("trending/", TrendingHashtagsView.as_view(), name="trending_hashtags"),
]

feed_patterns = [
    path("following/", FollowingFeedView.as_view(), name="following_feed"),
    path("explore/", ExploreFeedView.as_view(), name="explore_feed"),
]

notifications_patterns = [
    path("", NotificationListView.as_view(), name="notification_list"),
    path("mark-all-read/", NotificationListView.as_view(), name="notification_mark_all_read"),
    path("<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification_read"),
    path("unread-count/", NotificationUnreadCountView.as_view(), name="notification_unread_count"),
    path("devices/", PushDeviceView.as_view(), name="push_devices"),
]

admin_patterns = [
    path("stats/", AdminStatsView.as_view(), name="admin_stats"),
    path("users/", AdminUsersView.as_view(), name="admin_users"),
    path("users/<uuid:pk>/", AdminUserDetailView.as_view(), name="admin_user_detail"),
    path("reports/", AdminReportsView.as_view(), name="admin_reports"),
    path(
        "reports/<uuid:pk>/action/",
        AdminReportActionView.as_view(),
        name="admin_report_action",
    ),
    path("moderation-logs/", AdminModerationLogsView.as_view(), name="admin_moderation_logs"),
    path("feature-flags/", AdminFeatureFlagListView.as_view(), name="admin_feature_flags_list"),
    path(
        "feature-flags/<str:key>/",
        AdminFeatureFlagDetailView.as_view(),
        name="admin_feature_flags_detail",
    ),
]

urlpatterns = [
    path("auth/", include((auth_patterns, "auth"))),
    path("users/", include((users_patterns, "users"))),
    path("posts/", include((posts_patterns, "posts"))),
    path("social/", include((social_patterns, "social"))),
    path("hashtags/", include((hashtags_patterns, "hashtags"))),
    path("feed/", include((feed_patterns, "feed"))),
    path("notifications/", include((notifications_patterns, "notifications"))),
    path("reports/", CreateReportView.as_view(), name="create_report"),
    path("admin/", include((admin_patterns, "admin_api"))),
    path("feature-flags/", FeatureFlagsView.as_view(), name="feature_flags"),
]
