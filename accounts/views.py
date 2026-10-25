from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .models import Account
from videos.models import Comment, VideoStatus
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django import forms


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


class ProfileImageForm(forms.ModelForm):
    profile_image = forms.ImageField(required=True, widget=forms.FileInput(attrs={"accept": "image/*"}))

    class Meta:
        model = Account
        fields = ("profile_image",)


@login_required(login_url="login")
def profile(request):
    account, _ = Account.objects.get_or_create(user=request.user)
    form = ProfileImageForm(request.POST or None, request.FILES or None, instance=account)

    if request.method == "POST" and request.POST.get("action") == "remove_profile_image":
        image_name = account.profile_image.name
        if image_name and image_name != "videos/img/default-avatar.svg":
            account.profile_image.storage.delete(image_name)
        account.profile_image = "videos/img/default-avatar.svg"
        account.save(update_fields=["profile_image"])
        messages.success(request, "Your profile picture has been removed.")
        return redirect("profile")

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("profile")

    context = {
        "account": account,
        "form": form,
        "user_comments": Comment.objects.filter(author=request.user).select_related("video"),
        "video_statuses": VideoStatus.objects.filter(user=request.user).select_related("video").order_by("video__title"),
    }
    return render(request, "accounts/profile.html", context)
