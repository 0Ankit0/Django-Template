from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone

from .models import BillingCustomer, Invoice, Price, Product, Provider, WebhookEvent
from .services import build_invoice_pdf, create_stripe_customer, create_stripe_price, create_stripe_product, expire_one_time_subscriptions
from .services import process_stripe_webhook_event


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=300, retry_kwargs={"max_retries": 8})
def sync_product_to_stripe(self, product_id: int) -> None:
    close_old_connections()
    create_stripe_product(Product.objects.get(pk=product_id))


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=300, retry_kwargs={"max_retries": 8})
def sync_price_to_stripe(self, price_id: int) -> None:
    close_old_connections()
    price = Price.objects.select_related("product").get(pk=price_id)
    if not price.product.provider_product_id:
        create_stripe_product(price.product)
    create_stripe_price(price)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=300, retry_kwargs={"max_retries": 8})
def sync_customer_to_stripe(self, customer_id: int) -> None:
    close_old_connections()
    create_stripe_customer(BillingCustomer.objects.get(pk=customer_id, provider=Provider.STRIPE))


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=300, retry_kwargs={"max_retries": 8})
def process_stripe_webhook(self, webhook_event_id: int) -> None:
    close_old_connections()
    process_stripe_webhook_event(WebhookEvent.objects.get(pk=webhook_event_id, provider=Provider.STRIPE))


@shared_task
def retry_unprocessed_stripe_webhooks() -> int:
    close_old_connections()
    stale_before = timezone.now() - timedelta(minutes=10)
    ids = list(WebhookEvent.objects.filter(provider=Provider.STRIPE, processed=False).filter(Q(processing=False) | Q(processing=True, created_at__lt=stale_before)).values_list("pk", flat=True)[:100])
    for event_id in ids:
        process_stripe_webhook.delay(event_id)
    return len(ids)


@shared_task
def expire_one_time_purchases() -> int:
    close_old_connections()
    return expire_one_time_subscriptions()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=300, retry_kwargs={"max_retries": 8})
def generate_local_invoice(self, payment_id: int, billing_base_url: str) -> int:
    close_old_connections()
    from .models import Payment

    payment = Payment.objects.select_related("tenant", "subscription__price__product").get(pk=payment_id, provider__in=[Provider.KHALTI, Provider.ESEWA])
    if payment.status != Payment.Status.SUCCEEDED or not payment.subscription:
        return 0
    provider_invoice_id = f"{payment.provider}:{payment.provider_payment_id}"
    invoice, _ = Invoice.objects.get_or_create(
        provider=payment.provider,
        provider_invoice_id=provider_invoice_id,
        defaults={"tenant": payment.tenant, "subscription": payment.subscription, "number": f"INV-{payment.provider.upper()}-{payment.pk:08d}", "status": Invoice.Status.PAID, "amount_due": payment.amount, "amount_paid": payment.amount, "currency": payment.currency, "period_start": payment.subscription.current_period_start, "period_end": payment.subscription.current_period_end, "paid_at": payment.paid_at or timezone.now(), "metadata": {"payment_id": str(payment.pk), "provider_reference": payment.provider_payment_id}},
    )
    if not invoice.invoice_file:
        pdf = build_invoice_pdf(invoice_number=invoice.number, tenant_name=str(payment.tenant), provider=payment.provider, product_name=payment.subscription.price.product.name, amount=f"{payment.amount / 100:.2f}", currency=payment.currency, payment_reference=payment.provider_payment_id, issued_at=payment.paid_at or timezone.now(), period_end=payment.subscription.current_period_end)
        filename = f"billing/invoices/{invoice.number}.pdf"
        invoice.invoice_file.name = default_storage.save(filename, ContentFile(pdf, name=filename))
    invoice.invoice_pdf = f"{billing_base_url.rstrip('/')}/invoices/{invoice.pk}/download/"
    invoice.tenant = payment.tenant
    invoice.subscription = payment.subscription
    invoice.status = Invoice.Status.PAID
    invoice.amount_due = payment.amount
    invoice.amount_paid = payment.amount
    invoice.currency = payment.currency
    invoice.period_start = payment.subscription.current_period_start
    invoice.period_end = payment.subscription.current_period_end
    invoice.paid_at = payment.paid_at or invoice.paid_at or timezone.now()
    invoice.metadata = {**invoice.metadata, "payment_id": str(payment.pk), "provider_reference": payment.provider_payment_id}
    invoice.save()
    payment.provider_invoice_id = invoice.provider_invoice_id
    payment.save(update_fields=["provider_invoice_id", "updated_at"])
    return invoice.pk
