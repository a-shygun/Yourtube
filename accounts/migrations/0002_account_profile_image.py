from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='profile_image',
            field=models.ImageField(blank=True, upload_to='account_images'),
        ),
    ]
