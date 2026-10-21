from django.urls import path
from .views import UserLoginView, UserLogoutView, UserRegisterView, profile

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("register/", UserRegisterView.as_view(), name="register"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("profile/", profile, name="profile"),
]
