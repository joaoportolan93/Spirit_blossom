from django.urls import path

from .views import (
    BookmarkedPostListView,
    DraftDetailView,
    DraftListCreateView,
    PostBookmarkView,
    PostDetailView,
    PostLikeView,
    PostListCreateView,
    PostSearchView,
)

app_name = "posts"

urlpatterns = [
    path("", PostListCreateView.as_view(), name="post_list_create"),
    path("search/", PostSearchView.as_view(), name="post_search"),
    path("bookmarks/", BookmarkedPostListView.as_view(), name="post_bookmarks"),
    path("drafts/", DraftListCreateView.as_view(), name="draft_list_create"),
    path("drafts/<uuid:pk>/", DraftDetailView.as_view(), name="draft_detail"),
    path("<uuid:pk>/", PostDetailView.as_view(), name="post_detail"),
    path("<uuid:pk>/like/", PostLikeView.as_view(), name="post_like"),
    path("<uuid:pk>/bookmark/", PostBookmarkView.as_view(), name="post_bookmark"),
]
