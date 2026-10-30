from django.urls import path
from .views import BlockView, FollowView

app_name = "social"

urlpatterns = [
    path("follow/<str:username>/", FollowView.as_view(), name="follow"),
    path("block/<str:username>/", BlockView.as_view(), name="block"),
]
