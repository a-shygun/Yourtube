from django.contrib.auth.models import User
from django.db import models


DEFAULT_PROFILE_IMAGE = "videos/img/default-avatar.svg"


class Account(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image_url = models.URLField(null=True)
    profile_image = models.ImageField(default=DEFAULT_PROFILE_IMAGE, blank=True)

    def __str__(self):
        return self.user.username
