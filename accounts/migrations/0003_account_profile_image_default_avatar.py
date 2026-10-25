from django.db import migrations, models


DEFAULT_PROFILE_IMAGE = "videos/img/default-avatar.svg"


def set_default_profile_images(apps, schema_editor):
    Account = apps.get_model("accounts", "Account")
    Account.objects.filter(profile_image="").update(
        profile_image=DEFAULT_PROFILE_IMAGE
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_account_profile_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="account",
            name="profile_image",
            field=models.ImageField(
                blank=True,
                default=DEFAULT_PROFILE_IMAGE,
            ),
        ),
        migrations.RunPython(set_default_profile_images, migrations.RunPython.noop),
    ]
