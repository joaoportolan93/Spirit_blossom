from django.urls import path
from .views import PostDetailView, PostListCreateView, PostSearchView

app_name = "posts"

urlpatterns = [
    path("", PostListCreateView.as_view(), name="post_list_create"),
    path("search/", PostSearchView.as_view(), name="post_search"),
    path("<uuid:pk>/", PostDetailView.as_view(), name="post_detail"),
]
