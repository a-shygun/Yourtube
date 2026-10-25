from django.contrib import admin
from .models import Category, Channel, Comment, Playlist, Video, VideoStatus

# Register your models here.
admin.site.register([Video, VideoStatus, Category, Comment, Channel, Playlist])
