from django.urls import path

from .views import (
    BlockView,
    CloseFriendsListView,
    CloseFriendsView,
    FollowView,
    MuteView,
    ProfileDetailView,
)

app_name = "social"

urlpatterns = [
    path("follow/<str:username>/", FollowView.as_view(), name="follow"),
    path("block/<str:username>/", BlockView.as_view(), name="block"),
    path("mute/<str:username>/", MuteView.as_view(), name="mute"),
    path("close-friends/", CloseFriendsListView.as_view(), name="close-friends-list"),
    path("close-friends/<str:username>/", CloseFriendsView.as_view(), name="close-friends"),
    path("profile/<str:username>/", ProfileDetailView.as_view(), name="profile"),
]
