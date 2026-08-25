from django.db import migrations, models
import django.db.models.deletion


def migrate_existing_price_types(apps, schema_editor):
    Price = apps.get_model("billing", "Price")
    Price.objects.filter(interval="one_time").update(billing_type="one_time")


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_multi_provider")]

    operations = [
        migrations.AddField(
            model_name="price",
            name="billing_type",
            field=models.CharField(
                choices=[("one_time", "One time"), ("recurring", "Recurring"), ("expiring", "Expiring purchase")],
                default="recurring",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="price",
            name="interval",
            field=models.CharField(
                choices=[("one_time", "One time"), ("day", "Days"), ("week", "Weeks"), ("month", "Months"), ("year", "Years")],
                default="month",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="Entitlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("stripe", "Stripe"), ("khalti", "Khalti"), ("esewa", "eSewa")], max_length=32)),
                ("provider_reference", models.CharField(max_length=255)),
                ("starts_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("active", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("price", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="entitlements", to="billing.price")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="billing_entitlements", to="tenants.tenant")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["tenant", "active", "expires_at"], name="billing_ent_tenant_5b6b2a_idx")],
            },
        ),
        migrations.AddField(model_name="webhookevent", name="processing", field=models.BooleanField(default=False)),
        migrations.AddConstraint(
            model_name="entitlement",
            constraint=models.UniqueConstraint(fields=("provider", "provider_reference"), name="billing_entitlement_provider_reference_unique"),
        ),
        migrations.RunPython(migrate_existing_price_types, migrations.RunPython.noop),
    ]
