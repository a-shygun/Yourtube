from django import forms


class ProfileImageForm(forms.Form):
    profile_image = forms.ImageField(widget=forms.FileInput(attrs={"accept": "image/*"}))
