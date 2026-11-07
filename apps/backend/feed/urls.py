from django.urls import path

from .views import ExploreFeedView, FollowingFeedView

app_name = "feed"

urlpatterns = [
    path("following/", FollowingFeedView.as_view(), name="following_feed"),
    path("explore/", ExploreFeedView.as_view(), name="explore_feed"),
]
