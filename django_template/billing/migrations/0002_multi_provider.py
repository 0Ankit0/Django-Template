from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]
    operations = [
        migrations.RemoveConstraint(model_name="price", name="billing_price_interval_count_positive"),
        migrations.RenameField(model_name="price", old_name="provider_price_id", new_name="stripe_price_id"),
        migrations.RemoveField(model_name="product", name="provider"),
        migrations.RemoveField(model_name="product", name="provider_product_id"),
        migrations.AddField(model_name="product", name="stripe_product_id", field=models.CharField(blank=True, editable=False, max_length=255)),
        migrations.RemoveField(model_name="price", name="provider"),
        migrations.AddField(model_name="billingcustomer", name="provider", field=models.CharField(choices=[("stripe", "Stripe"), ("khalti", "Khalti"), ("esewa", "eSewa")], default="stripe", max_length=32)),
        migrations.AlterField(model_name="billingcustomer", name="tenant", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="billing_customers", to="tenants.tenant")),
        migrations.AlterField(model_name="billingcustomer", name="provider_customer_id", field=models.CharField(max_length=255)),
        migrations.AlterField(model_name="subscription", name="provider", field=models.CharField(choices=[("stripe", "Stripe"), ("khalti", "Khalti"), ("esewa", "eSewa")], default="stripe", max_length=32)),
        migrations.AlterField(model_name="subscription", name="provider_subscription_id", field=models.CharField(max_length=255)),
        migrations.AlterField(model_name="payment", name="provider", field=models.CharField(choices=[("stripe", "Stripe"), ("khalti", "Khalti"), ("esewa", "eSewa")], default="stripe", max_length=32)),
        migrations.AlterField(model_name="payment", name="provider_payment_id", field=models.CharField(max_length=255)),
        migrations.AddField(model_name="invoice", name="provider", field=models.CharField(choices=[("stripe", "Stripe"), ("khalti", "Khalti"), ("esewa", "eSewa")], default="stripe", max_length=32)),
        migrations.AlterField(model_name="invoice", name="provider_invoice_id", field=models.CharField(max_length=255)),
        migrations.AddField(model_name="checkoutsession", name="provider", field=models.CharField(choices=[("stripe", "Stripe"), ("khalti", "Khalti"), ("esewa", "eSewa")], default="stripe", max_length=32)),
        migrations.AlterField(model_name="checkoutsession", name="provider_session_id", field=models.CharField(max_length=255)),
        migrations.AlterField(model_name="webhookevent", name="provider", field=models.CharField(choices=[("stripe", "Stripe"), ("khalti", "Khalti"), ("esewa", "eSewa")], default="stripe", max_length=32)),
        migrations.AlterField(model_name="webhookevent", name="event_id", field=models.CharField(max_length=255)),
        migrations.AddConstraint(model_name="billingcustomer", constraint=models.UniqueConstraint(fields=("tenant", "provider"), name="billing_customer_tenant_provider_unique")),
        migrations.AddConstraint(model_name="billingcustomer", constraint=models.UniqueConstraint(fields=("provider", "provider_customer_id"), name="billing_customer_provider_id_unique")),
        migrations.AddConstraint(model_name="subscription", constraint=models.UniqueConstraint(fields=("provider", "provider_subscription_id"), name="billing_subscription_provider_id_unique")),
        migrations.AddConstraint(model_name="payment", constraint=models.UniqueConstraint(fields=("provider", "provider_payment_id"), name="billing_payment_provider_id_unique")),
        migrations.AddConstraint(model_name="invoice", constraint=models.UniqueConstraint(fields=("provider", "provider_invoice_id"), name="billing_invoice_provider_id_unique")),
        migrations.AddConstraint(model_name="checkoutsession", constraint=models.UniqueConstraint(fields=("provider", "provider_session_id"), name="billing_checkout_provider_id_unique")),
        migrations.AddConstraint(model_name="webhookevent", constraint=models.UniqueConstraint(fields=("provider", "event_id"), name="billing_webhook_provider_event_unique")),
    ]
