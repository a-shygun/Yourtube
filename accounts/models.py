import uuid

from django.db import models
from django.contrib.auth.models import User
from PIL import Image

# Create your models here.


class Account(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image_url = models.URLField(null=True)
    profile_image = models.ImageField(default="videos/img/default-avatar.svg", blank=True)

    def save(self, *args, **kwargs):
        if not self.profile_image or self.profile_image._committed:
            return super().save(*args, **kwargs)

        old_image_name = type(self).objects.filter(pk=self.pk).values_list("profile_image", flat=True).first()
        self.profile_image.name = f"profile-{self.user_id}-{uuid.uuid4().hex}.jpg"

        super().save(*args, **kwargs)

        with Image.open(self.profile_image.path) as image:
            image.thumbnail((360, 360))
            image.convert("RGB").save(self.profile_image.path, format="JPEG")

        if old_image_name and old_image_name != "videos/img/default-avatar.svg":
            self.profile_image.storage.delete(old_image_name)

    def __str__(self):
        return self.user.username
