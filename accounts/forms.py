from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


class StyledFieldsMixin:
    field_class = (
        "mt-1 block w-full border border-input-border bg-surface-alt "
        "px-3 py-2.5 text-sm text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = self.field_class


class UsernameAuthenticationForm(StyledFieldsMixin, AuthenticationForm):
    pass


class UsernameCreationForm(StyledFieldsMixin, UserCreationForm):
    pass


class ProfileImageForm(forms.Form):
    profile_image = forms.ImageField()
