from django.db import migrations, models


def migrate_price_semantics(apps, schema_editor):
    Price = apps.get_model("billing", "Price")
    for price in Price.objects.all().iterator():
        metadata = dict(price.metadata or {})
        if price.interval == "one_time":
            price.interval = "month"
            price.interval_count = 1
            metadata["one_time"] = True
            price.metadata = metadata
            price.save(update_fields=["interval", "interval_count", "metadata"])
        elif metadata.get("billing_type") == "expiring":
            metadata.pop("billing_type", None)
            metadata["one_time"] = True
            price.interval_count = 1
            price.metadata = metadata
            price.save(update_fields=["interval_count", "metadata"])


class Migration(migrations.Migration):
    dependencies = [("billing", "0003_entitlements_and_price_billing_type")]
    operations = [
        migrations.RunPython(migrate_price_semantics, migrations.RunPython.noop),
        migrations.RemoveField(model_name="price", name="billing_type"),
        migrations.DeleteModel(name="Entitlement"),
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
