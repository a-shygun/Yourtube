from django.contrib import admin
from .models import Category, Channel, Comment, Video

# Register your models here.
admin.site.register([Video, Category, Comment, Channel])
