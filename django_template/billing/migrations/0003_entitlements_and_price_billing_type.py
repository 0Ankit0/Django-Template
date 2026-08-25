from django.db import migrations, models


def migrate_price_interval_semantics(apps, schema_editor):
    Price = apps.get_model("billing", "Price")
    for price in Price.objects.all().iterator():
        metadata = dict(price.metadata or {})
        if price.interval == "one_time":
            price.interval = "month"
            price.interval_count = 1
            metadata["one_time"] = True
            price.metadata = metadata
            price.save(update_fields=["interval", "interval_count", "metadata"])


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_multi_provider")]

    operations = [
        migrations.AddField(model_name="webhookevent", name="processing", field=models.BooleanField(default=False)),
        migrations.RunPython(migrate_price_interval_semantics, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="price",
            name="interval",
            field=models.CharField(
                choices=[("day", "Days"), ("week", "Weeks"), ("month", "Months"), ("year", "Years")],
                default="month",
                max_length=20,
            ),
        ),
    ]
