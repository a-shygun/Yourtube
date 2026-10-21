from django.db import models
from django.contrib.auth.models import User 

# Create your models here.

class Account(models.Model):
  user = models.OneToOneField(User, on_delete=models.CASCADE)
  image_url = models.URLField(null=True)
  profile_image = models.ImageField(upload_to='account_images', blank=True)
  
  def __str__(self):
    return self.user.username
