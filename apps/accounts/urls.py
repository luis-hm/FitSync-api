from django.urls import path

from apps.accounts.views import (
    AuthRootAPIView,
    LoginAPIView,
    LogoutAPIView,
    MeAPIView,
    PasswordResetAPIView,
    PasswordResetConfirmAPIView,
    RefreshAPIView,
    RegisterAPIView,
)


app_name = "accounts"

urlpatterns = [
    path("", AuthRootAPIView.as_view(), name="auth-root"),
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("refresh/", RefreshAPIView.as_view(), name="refresh"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("me/", MeAPIView.as_view(), name="me"),
    path("password-reset/", PasswordResetAPIView.as_view(), name="password-reset"),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmAPIView.as_view(),
        name="password-reset-confirm",
    ),
]
