from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="ProviderConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("stripe", "Stripe"), ("khalti", "Khalti"), ("esewa", "eSewa")], max_length=32, unique=True)),
                ("enabled", models.BooleanField(default=True)),
                ("environment", models.CharField(choices=[("sandbox", "Sandbox / Test"), ("live", "Live / Production")], default="sandbox", max_length=16)),
                ("notes", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["provider"]},
        ),
        migrations.RunPython(
            lambda apps, schema_editor: [
                apps.get_model("billing", "ProviderConfiguration").objects.get_or_create(provider=provider, defaults={"enabled": True, "environment": "sandbox"})
                for provider in ("stripe", "khalti", "esewa")
            ],
            migrations.RunPython.noop,
        ),
    ]
