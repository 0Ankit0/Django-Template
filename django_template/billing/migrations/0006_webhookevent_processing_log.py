from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_alter_checkoutsession_url_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="webhookevent",
            name="processing_log",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
