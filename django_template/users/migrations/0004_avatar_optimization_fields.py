from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0003_user_avatar_user_bio_user_language_user_timezone")]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="avatar",
            field=models.ImageField(blank=True, null=True, upload_to="avatars/source/"),
        ),
        migrations.AddField(
            model_name="user",
            name="avatar_thumbnail",
            field=models.ImageField(blank=True, editable=False, null=True, upload_to="avatars/thumbnail/"),
        ),
    ]
