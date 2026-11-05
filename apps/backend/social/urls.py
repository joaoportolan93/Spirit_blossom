from django.urls import path

from .views import BlockView, FollowView, ProfileDetailView

app_name = "social"

urlpatterns = [
    path("follow/<str:username>/", FollowView.as_view(), name="follow"),
    path("block/<str:username>/", BlockView.as_view(), name="block"),
    path("profile/<str:username>/", ProfileDetailView.as_view(), name="profile"),
]
