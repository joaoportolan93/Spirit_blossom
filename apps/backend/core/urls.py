"""
URLs agregadas do app core (estilo Lumem).
Preserva todas as rotas públicas, caminhos e namespaces.
"""

from django.urls import include, path

from core.views.auth import (
    CSRFView,
    GoogleAuthView,
    GoogleCompleteSignupView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    TokenRefreshView,
    UserDataExportView,
    UserProfileUpdateView,
    UserSearchView,
)
from core.views.feed import ExploreFeedView, FollowingFeedView
from core.views.notifications import NotificationListView, NotificationMarkReadView
from core.views.posts import (
    BookmarkedPostListView,
    DraftDetailView,
    DraftListCreateView,
    PostBookmarkView,
    PostDetailView,
    PostLikeView,
    PostListCreateView,
    PostSearchView,
)
from core.views.social import (
    BlockedUsersListView,
    BlockView,
    CloseFriendsCandidatesView,
    CloseFriendsListView,
    CloseFriendsView,
    FollowRequestAcceptView,
    FollowRequestListView,
    FollowRequestRejectView,
    FollowView,
    MutedUsersListView,
    MuteView,
    ProfileDetailView,
)

auth_patterns = [
    path("csrf/", CSRFView.as_view(), name="csrf"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
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
    path("profile/", UserProfileUpdateView.as_view(), name="profile_update"),
    path("search/", UserSearchView.as_view(), name="search"),
    path("export-data/", UserDataExportView.as_view(), name="export_data"),
]

posts_patterns = [
    path("", PostListCreateView.as_view(), name="post_list_create"),
    path("search/", PostSearchView.as_view(), name="post_search"),
    path("bookmarks/", BookmarkedPostListView.as_view(), name="post_bookmarks"),
    path("drafts/", DraftListCreateView.as_view(), name="draft_list_create"),
    path("drafts/<uuid:pk>/", DraftDetailView.as_view(), name="draft_detail"),
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
]

feed_patterns = [
    path("following/", FollowingFeedView.as_view(), name="following_feed"),
    path("explore/", ExploreFeedView.as_view(), name="explore_feed"),
]

notifications_patterns = [
    path("", NotificationListView.as_view(), name="notification_list"),
    path("mark-all-read/", NotificationListView.as_view(), name="notification_mark_all_read"),
    path("<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification_read"),
]

urlpatterns = [
    path("auth/", include((auth_patterns, "accounts"))),
    path("users/", include((users_patterns, "users"))),
    path("posts/", include((posts_patterns, "posts"))),
    path("social/", include((social_patterns, "social"))),
    path("feed/", include((feed_patterns, "feed"))),
    path("notifications/", include((notifications_patterns, "notifications"))),
]
