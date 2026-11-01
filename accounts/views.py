import uuid
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.files.base import ContentFile
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView
from PIL import Image

from .forms import ProfileImageForm
from .models import Account, DEFAULT_PROFILE_IMAGE
from videos.models import Video
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


class UserLoginView(SuccessMessageMixin, LoginView):
    authentication_form = AuthenticationForm
    redirect_authenticated_user = True
    success_message = "You have logged in successfully."


class UserRegisterView(SuccessMessageMixin, CreateView):
    model = User
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    success_message = "Your account has been created. You can now log in."


class UserLogoutView(LogoutView):
    def post(self, request, *args, **kwargs):
        messages.success(request, "You have been logged out.")
        return super().post(request, *args, **kwargs)


@login_required(login_url="login")
def profile(request):
    account, _ = Account.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileImageForm(request.POST, request.FILES)
        if request.POST.get("action") == "remove_profile_image":
            image_name = account.profile_image.name
            if image_name and image_name != DEFAULT_PROFILE_IMAGE:
                account.profile_image.storage.delete(image_name)
            account.profile_image = DEFAULT_PROFILE_IMAGE
            account.save()
            messages.success(request, "Your profile picture has been removed.")
            return redirect("profile")

        if form.is_valid():
            old_image = account.profile_image.name
            with Image.open(form.cleaned_data["profile_image"]) as image:
                image.thumbnail((360, 360))
                output = BytesIO()
                image.convert("RGB").save(output, format="JPEG")

            account.profile_image.save(
                f"profile-{uuid.uuid4().hex}.jpg",
                ContentFile(output.getvalue()),
            )
            if old_image and old_image != DEFAULT_PROFILE_IMAGE:
                account.profile_image.storage.delete(old_image)

            messages.success(request, "Your profile has been updated.")
            return redirect("profile")
    else:
        form = ProfileImageForm()

    favorite_videos = Video.objects.filter(is_fav=True).select_related("channel")
    favorite_videos = favorite_videos.order_by("title")

    return render(
        request,
        "accounts/profile.html",
        {"account": account, "form": form, "favorite_videos": favorite_videos},
    )
