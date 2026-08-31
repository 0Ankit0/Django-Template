from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0006_webhookevent_processing_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="amount_total",
            field=models.PositiveBigIntegerField(default=0),
        ),
    ]
