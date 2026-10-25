from django.urls import path
from .views import profile
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import CreateView
from .views import UserLoginView, UserLogoutView, UserRegisterView

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"), 
    path("register/", UserRegisterView.as_view(), name="register"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("profile/", profile, name="profile"),
]
