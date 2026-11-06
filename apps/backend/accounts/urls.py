from django.urls import path

from .views import (
    CSRFView,
    GoogleAuthView,
    GoogleCompleteSignupView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    TokenRefreshView,
)

app_name = "accounts"

urlpatterns = [
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
