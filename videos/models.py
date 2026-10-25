from django.db import models

from django.contrib.auth.models import User
from videos.management.media_location import get_media_root


def media_file_path(relative_path):
    if not relative_path:
        return None
    media_root = get_media_root()
    if not media_root:
        return None
    candidate = (media_root / relative_path).resolve()
    return candidate if candidate.is_relative_to(media_root) and candidate.is_file() else None


class Channel(models.Model):
    name = models.CharField(max_length=200)
    follower_count = models.IntegerField()
    is_verified = models.BooleanField()
    url = models.URLField(max_length=500)
    owner = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Playlist(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    modified_date = models.DateField()
    view_count = models.PositiveBigIntegerField()
    video_count = models.IntegerField()
    thumbnail_loc = models.CharField(max_length=500, blank=True)
    url = models.URLField(max_length=500)
    creator = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Video(models.Model):
    title = models.CharField(max_length=200)
    video_loc = models.CharField(max_length=500, blank=True)
    thumbnail_loc = models.CharField(max_length=500)
    thumbnail_url = models.URLField(max_length=500)
    description = models.TextField(blank=True)
    duration = models.IntegerField()
    view_count = models.PositiveBigIntegerField()
    video_url = models.URLField(max_length=500)
    comment_count = models.IntegerField()
    like_count = models.IntegerField(default=0)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    playlist = models.ForeignKey(Playlist, on_delete=models.SET_NULL, null=True, blank=True)
    upload_date = models.DateField()
    position_in_playlist = models.IntegerField(null=True, blank=True)
    resolution = models.CharField(max_length=200)
    categories = models.ManyToManyField(Category, blank=True)

    def __str__(self):
        return self.title


class VideoStatus(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="user_statuses")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="video_statuses")
    status = models.CharField(
        max_length=10,
        choices=(("watched", "Watched"), ("to-watch", "To watch")),
    )


class Comment(models.Model):
    source_id = models.CharField(max_length=200)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    like_count = models.PositiveIntegerField(default=0)
    timestamp = models.DateTimeField()

    def __str__(self):
        return f"{self.author.username}: {self.text[:40]}"
