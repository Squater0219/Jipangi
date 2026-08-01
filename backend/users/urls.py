from django.urls import path

from .views import LoginView, LogoutView, MeView, RefreshView, SignupView


urlpatterns = [
    path("auth/signup", SignupView.as_view(), name="signup"),
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/token/refresh", RefreshView.as_view(), name="token-refresh"),
    path("auth/logout", LogoutView.as_view(), name="logout"),
    path("users/me", MeView.as_view(), name="me"),
]
