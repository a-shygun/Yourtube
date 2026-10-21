from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("videos", "0011_video_thumbnail_loc_length"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="video",
            name="liked_by",
        ),
        migrations.AddField(
            model_name="video",
            name="watched_by",
            field=models.ManyToManyField(
                blank=True,
                related_name="watched_videos",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="video",
            name="to_watch_by",
            field=models.ManyToManyField(
                blank=True,
                related_name="videos_to_watch",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
