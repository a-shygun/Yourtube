from django.contrib import admin
from .models import Category, Channel, Comment, Playlist, Tag, Video

# Register your models here.
admin.site.register([Tag, Video, Category, Comment, Channel, Playlist])
