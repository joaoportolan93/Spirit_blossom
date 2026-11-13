from django.urls import path

from comments.views import (
    CommentBookmarksListView,
    CommentBookmarkView,
    CommentDetailView,
    CommentHideView,
    CommentLikeView,
    CommentRepliesView,
    CommentThreadView,
    PostCommentsView,
    PostHiddenCommentsView,
)

urlpatterns = [
    path("posts/<uuid:pk>/comments/", PostCommentsView.as_view(), name="post-comments"),
    path(
        "posts/<uuid:pk>/hidden-comments/",
        PostHiddenCommentsView.as_view(),
        name="post-hidden-comments",
    ),
    path("comments/bookmarks/", CommentBookmarksListView.as_view(), name="comment-bookmarks-list"),
    path("comments/<uuid:pk>/", CommentDetailView.as_view(), name="comment-detail"),
    path("comments/<uuid:pk>/replies/", CommentRepliesView.as_view(), name="comment-replies"),
    path("comments/<uuid:pk>/thread/", CommentThreadView.as_view(), name="comment-thread"),
    path("comments/<uuid:pk>/like/", CommentLikeView.as_view(), name="comment-like"),
    path("comments/<uuid:pk>/bookmark/", CommentBookmarkView.as_view(), name="comment-bookmark"),
    path("comments/<uuid:pk>/hide/", CommentHideView.as_view(), name="comment-hide"),
]
