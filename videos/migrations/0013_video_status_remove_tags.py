from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_watch_statuses(apps, schema_editor):
    Video = apps.get_model("videos", "Video")
    VideoStatus = apps.get_model("videos", "VideoStatus")
    alias = schema_editor.connection.alias

    watched = Video._meta.get_field("watched_by").remote_field.through
    to_watch = Video._meta.get_field("to_watch_by").remote_field.through
    statuses = [
        VideoStatus(video_id=video_id, user_id=user_id, status="watched")
        for video_id, user_id in watched.objects.using(alias).values_list("video_id", "user_id")
    ]
    watched_pairs = {(status.video_id, status.user_id) for status in statuses}
    statuses.extend(
        VideoStatus(video_id=video_id, user_id=user_id, status="to-watch")
        for video_id, user_id in to_watch.objects.using(alias).values_list("video_id", "user_id")
        if (video_id, user_id) not in watched_pairs
    )
    VideoStatus.objects.using(alias).bulk_create(statuses, batch_size=1000)


def restore_watch_statuses(apps, schema_editor):
    Video = apps.get_model("videos", "Video")
    VideoStatus = apps.get_model("videos", "VideoStatus")
    alias = schema_editor.connection.alias
    watched = Video._meta.get_field("watched_by").remote_field.through
    to_watch = Video._meta.get_field("to_watch_by").remote_field.through

    watched_rows = []
    to_watch_rows = []
    for video_id, user_id, status in VideoStatus.objects.using(alias).values_list("video_id", "user_id", "status"):
        through_row = {"video_id": video_id, "user_id": user_id}
        if status == "watched":
            watched_rows.append(watched(**through_row))
        elif status == "to-watch":
            to_watch_rows.append(to_watch(**through_row))
    watched.objects.using(alias).bulk_create(watched_rows, ignore_conflicts=True, batch_size=1000)
    to_watch.objects.using(alias).bulk_create(to_watch_rows, ignore_conflicts=True, batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("videos", "0012_video_watch_statuses"),
    ]

    operations = [
        migrations.CreateModel(
            name="VideoStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("watched", "Watched"), ("to-watch", "To watch")], max_length=10)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="video_statuses", to=settings.AUTH_USER_MODEL)),
                ("video", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_statuses", to="videos.video")),
            ],
            options={
                "unique_together": {("video", "user")},
            },
        ),
        migrations.RunPython(copy_watch_statuses, restore_watch_statuses),
        migrations.RemoveField(model_name="video", name="watched_by"),
        migrations.RemoveField(model_name="video", name="to_watch_by"),
        migrations.RemoveField(model_name="video", name="tags"),
        migrations.DeleteModel(name="Tag"),
    ]
