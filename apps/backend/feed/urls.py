from django.urls import path

from .views import FollowingFeedView

app_name = "feed"

urlpatterns = [
    path("following/", FollowingFeedView.as_view(), name="following_feed"),
]
