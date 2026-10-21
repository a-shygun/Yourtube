from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import ProfileImageForm, UsernameAuthenticationForm, UsernameCreationForm
from .models import Account
from videos.models import Comment, Video
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image


class UserLoginView(SuccessMessageMixin, LoginView):
    redirect_authenticated_user = True
    success_message = "You have logged in successfully."
    authentication_form = UsernameAuthenticationForm


class UserRegisterView(SuccessMessageMixin, CreateView):
    model = User
    form_class = UsernameCreationForm
    success_url = reverse_lazy("login")
    success_message = "Your account has been created. You can now log in."


class UserLogoutView(SuccessMessageMixin, LogoutView):
    def post(self, request, *args, **kwargs):
        messages.success(request, "You have been logged out.")
        return super().post(request, *args, **kwargs)


@login_required(login_url="login")
def profile(request):
    def make_profile_image(image_file, filename):
        image = Image.open(image_file).convert("RGB").resize((360, 360))
        output = BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        return ContentFile(output.getvalue(), name=filename)

    account, _ = Account.objects.get_or_create(user=request.user)
    is_post = request.method == "POST"

    form = ProfileImageForm(
        request.POST if is_post else None,
        request.FILES if is_post else None,
    )

    if is_post and form.is_valid():
        old_image_name = account.profile_image.name
        filename = f"profile-{account.user_id}.jpg"

        account.profile_image.save(
            filename,
            make_profile_image(form.cleaned_data["profile_image"], filename),
            save=False,
        )

        if old_image_name:
            account.profile_image.storage.delete(old_image_name)

        account.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("profile")

    context = {
        "account": account,
        "form": form,
        "user_comments": Comment.objects.filter(author=request.user)
        .select_related("video")
        .order_by("-timestamp")[:50],
        "watched_videos": Video.objects.filter(watched_by=request.user)
        .select_related("channel")
        .order_by("-pk")[:50],
        "to_watch_videos": Video.objects.filter(to_watch_by=request.user)
        .select_related("channel")
        .order_by("-pk")[:50],
    }
    return render(request, "accounts/profile.html", context)
