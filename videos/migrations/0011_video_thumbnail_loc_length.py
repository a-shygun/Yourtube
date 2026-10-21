from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("videos", "0010_playlist_thumbnail_loc"),
    ]

    operations = [
        migrations.AlterField(
            model_name="video",
            name="thumbnail_loc",
            field=models.CharField(max_length=500),
        ),
    ]
