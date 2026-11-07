from django.contrib.auth.models import User
from django.db import models


class Channel(models.Model):
    name = models.CharField(max_length=200)
    follower_count = models.PositiveIntegerField()
    is_verified = models.BooleanField()
    url = models.URLField(max_length=500, blank=True)
    owner = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name="video_categories"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("name",), condition=models.Q(owner__isnull=True), name="unique_library_category_name"
            ),
            models.UniqueConstraint(
                fields=("owner", "name"), condition=models.Q(owner__isnull=False), name="unique_user_category_name"
            ),
        ]

    def __str__(self):
        return self.name


class Video(models.Model):
    WATCH_STATUS_CHOICES = (
        ("none", "None"),
        ("to-watch", "To watch"),
        ("watched", "Watched"),
    )

    title = models.CharField(max_length=200)
    video_loc = models.CharField(max_length=500, blank=True)
    thumbnail_loc = models.CharField(max_length=500, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    duration = models.PositiveIntegerField()
    view_count = models.PositiveBigIntegerField()
    video_url = models.URLField(max_length=500, blank=True)
    comment_count = models.PositiveIntegerField()
    like_count = models.PositiveIntegerField(default=0)
    is_fav = models.BooleanField(default=False)
    watch_status = models.CharField(max_length=10, choices=WATCH_STATUS_CHOICES, default="none")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    upload_date = models.DateField()
    resolution = models.CharField(max_length=200)
    categories = models.ManyToManyField(Category, blank=True)

    def __str__(self):
        return self.title



class Comment(models.Model):
    source_id = models.CharField(max_length=200)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    like_count = models.PositiveIntegerField(default=0)
    timestamp = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("video", "source_id"), name="unique_video_comment_source"
            )
        ]

    def __str__(self):
        return f"{self.author.username}: {self.text[:40]}"
