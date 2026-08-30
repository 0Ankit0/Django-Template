from django.db import migrations, models


def normalize_billing_data(apps, schema_editor):
    Product = apps.get_model("billing", "Product")
    Price = apps.get_model("billing", "Price")
    BillingCustomer = apps.get_model("billing", "BillingCustomer")
    Subscription = apps.get_model("billing", "Subscription")
    Payment = apps.get_model("billing", "Payment")
    Invoice = apps.get_model("billing", "Invoice")
    CheckoutSession = apps.get_model("billing", "CheckoutSession")

    for model in (Product, Price, BillingCustomer, Subscription, Payment, Invoice, CheckoutSession):
        model.objects.filter(provider_product_id="").update(provider_product_id=None) if model is Product else None
        model.objects.filter(provider_price_id="").update(provider_price_id=None) if model is Price else None
        model.objects.filter(provider_customer_id="").update(provider_customer_id=None) if model in (BillingCustomer, Subscription) else None
        model.objects.filter(provider_subscription_id="").update(provider_subscription_id=None) if model is Subscription else None
        model.objects.filter(provider_payment_id="").update(provider_payment_id=None) if model is Payment else None
        model.objects.filter(provider_invoice_id="").update(provider_invoice_id=None) if model is Invoice else None
        model.objects.filter(provider_session_id="").update(provider_session_id=None) if model is CheckoutSession else None

    for model in (Price, Payment, Invoice):
        model.objects.filter(currency="npr").update(currency="NPR")
        model.objects.filter(currency="usd").update(currency="USD")


def restore_billing_data(apps, schema_editor):
    Price = apps.get_model("billing", "Price")
    Payment = apps.get_model("billing", "Payment")
    Invoice = apps.get_model("billing", "Invoice")
    for model in (Price, Payment, Invoice):
        model.objects.filter(currency="NPR").update(currency="npr")
        model.objects.filter(currency="USD").update(currency="usd")


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_providerconfiguration_and_more")]

    operations = [
        migrations.RunPython(normalize_billing_data, restore_billing_data),
        migrations.AlterField(model_name="product", name="provider_product_id", field=models.CharField(blank=True, max_length=255, null=True, unique=True, editable=False)),
        migrations.AlterField(model_name="price", name="provider_price_id", field=models.CharField(blank=True, max_length=255, null=True, unique=True, editable=False)),
        migrations.AlterField(model_name="price", name="currency", field=models.CharField(choices=[("NPR", "Nepalese Rupee"), ("USD", "US Dollar")], default="NPR", max_length=3)),
        migrations.AlterField(model_name="billingcustomer", name="provider_customer_id", field=models.CharField(blank=True, max_length=255, null=True, unique=True, editable=False)),
        migrations.AlterField(model_name="subscription", name="provider_subscription_id", field=models.CharField(blank=True, max_length=255, null=True, unique=True, editable=False)),
        migrations.AlterField(model_name="subscription", name="provider_customer_id", field=models.CharField(blank=True, max_length=255, null=True, editable=False)),
        migrations.AlterField(model_name="payment", name="provider_payment_id", field=models.CharField(blank=True, max_length=255, null=True, unique=True, editable=False)),
        migrations.AlterField(model_name="payment", name="provider_invoice_id", field=models.CharField(blank=True, max_length=255, null=True, editable=False)),
        migrations.AlterField(model_name="payment", name="currency", field=models.CharField(choices=[("NPR", "Nepalese Rupee"), ("USD", "US Dollar")], default="NPR", max_length=3)),
        migrations.AlterField(model_name="invoice", name="provider_invoice_id", field=models.CharField(blank=True, max_length=255, null=True, unique=True, editable=False)),
        migrations.AlterField(model_name="invoice", name="currency", field=models.CharField(choices=[("NPR", "Nepalese Rupee"), ("USD", "US Dollar")], default="NPR", max_length=3)),
        migrations.AlterField(model_name="checkoutsession", name="provider_session_id", field=models.CharField(blank=True, max_length=255, null=True, unique=True, editable=False)),
    ]
