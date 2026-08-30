from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Any

import calendar
from datetime import timedelta

import stripe
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from ..models import BillingCustomer, CheckoutSession, Invoice, Payment, Price, Product, Provider, Subscription


def _stripe_client() -> stripe.StripeClient:
    key = getattr(settings, "STRIPE_SECRET_KEY", "")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    return stripe.StripeClient(key)


def _stripe_dict(resource: Any) -> dict[str, Any]:
    if isinstance(resource, dict):
        return resource
    if hasattr(resource, "to_dict_recursive"):
        return resource.to_dict_recursive()
    if hasattr(resource, "to_dict"):
        return resource.to_dict()
    return dict(resource)


def _stripe_request(
    path: str,
    data: dict[str, Any] | None = None,
    method: str = "POST",
) -> dict[str, Any]:
    if method != "POST":
        raise NotImplementedError("Only Stripe create operations are supported here.")
    client = _stripe_client()
    payload = data or {}
    if path == "/products":
        return _stripe_dict(client.v1.products.create(payload))
    if path == "/prices":
        return _stripe_dict(client.v1.prices.create(payload))
    raise NotImplementedError(f"Unsupported Stripe endpoint: {path}")


def _dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value), tz=dt_timezone.utc)


def create_stripe_product(product: Product) -> Product:
    if product.provider_product_id:
        return product
    data = _stripe_dict(
        _stripe_client().v1.products.create(
            {
                "name": product.name,
                "description": product.description,
                "active": product.active,
                "metadata": {
                    "local_product_id": str(product.pk),
                    **{str(k): str(v) for k, v in product.metadata.items()},
                },
            },
            options={"idempotency_key": f"billing-product-{product.pk}"},
        ),
    )
    Product.objects.filter(
        pk=product.pk,
        provider_product_id__isnull=True,
    ).update(provider_product_id=data["id"], updated_at=timezone.now())
    product.provider_product_id = data["id"]
    return product


def create_stripe_price(price: Price) -> Price:
    if price.provider_price_id:
        return price
    product = price.product
    if not product.provider_product_id:
        raise ValueError("Product must have a Stripe product ID before creating a Stripe price.")
    params: dict[str, Any] = {
        "product": product.provider_product_id,
        "unit_amount": price.amount,
        "currency": price.currency.lower(),
        "active": price.active,
        "metadata": {
            "local_price_id": str(price.pk),
            **{str(k): str(v) for k, v in price.metadata.items()},
        },
    }
    if price.is_recurring:
        params["recurring"] = {
            "interval": price.interval,
            "interval_count": price.interval_count,
        }
    data = _stripe_dict(
        _stripe_client().v1.prices.create(
            params,
            options={"idempotency_key": f"billing-price-{price.pk}"},
        ),
    )
    Price.objects.filter(
        pk=price.pk,
        provider_price_id__isnull=True,
    ).update(provider_price_id=data["id"], updated_at=timezone.now())
    price.provider_price_id = data["id"]
    return price


def create_stripe_customer(customer: BillingCustomer) -> BillingCustomer:
    if customer.provider_customer_id:
        return customer
    data = _stripe_dict(
        _stripe_client().v1.customers.create(
            {
                "email": customer.email or None,
                "name": customer.name or None,
                "metadata": {
                    "tenant_id": str(customer.tenant_id),
                    "local_customer_id": str(customer.pk),
                },
            },
            options={"idempotency_key": f"billing-customer-{customer.pk}"},
        ),
    )
    BillingCustomer.objects.filter(
        pk=customer.pk,
        provider_customer_id__isnull=True,
    ).update(provider_customer_id=data["id"], updated_at=timezone.now())
    customer.provider_customer_id = data["id"]
    return customer


def create_or_get_customer(
    tenant,
    email: str = "",
    name: str = "",
) -> BillingCustomer:
    customer, _ = BillingCustomer.objects.get_or_create(
        tenant=tenant,
        provider=Provider.STRIPE,
        defaults={"email": email, "name": name},
    )
    changed = False
    if email and customer.email != email:
        customer.email = email
        changed = True
    if name and customer.name != name:
        customer.name = name
        changed = True
    if changed:
        customer.save(update_fields=["email", "name", "updated_at"])
    if not customer.provider_customer_id:
        create_stripe_customer(customer)
    return customer


def create_checkout_session(request, price: Price) -> CheckoutSession:
    if not price.provider_price_id:
        raise ValueError("This price has not been synchronized to Stripe yet.")
    tenant = request.tenant
    customer = create_or_get_customer(
        tenant,
        getattr(request.user, "email", ""),
        getattr(request.user, "name", "") or str(request.user),
    )
    mode = CheckoutSession.Mode.PAYMENT if price.is_one_time else CheckoutSession.Mode.SUBSCRIPTION
    metadata = {"tenant_id": str(tenant.pk), "price_id": str(price.pk)}
    payload: dict[str, Any] = {
        "mode": mode,
        "customer": customer.provider_customer_id,
        "line_items": [{"price": price.provider_price_id, "quantity": 1}],
        "success_url": request.build_absolute_uri(
            "/billing/success/",
        ) + "?provider=stripe&session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": request.build_absolute_uri(
            f"/billing/cancelled/?provider=stripe&price_id={price.pk}",
        ),
        "client_reference_id": str(tenant.pk),
        "metadata": metadata,
    }
    if price.is_one_time:
        payload["payment_intent_data"] = {"metadata": metadata}
        payload["invoice_creation"] = {
            "enabled": True,
            "invoice_data": {"metadata": metadata},
        }
    else:
        payload["subscription_data"] = {"metadata": metadata}
    data = _stripe_dict(_stripe_client().v1.checkout.sessions.create(payload))
    return CheckoutSession.objects.create(
        tenant=tenant,
        price=price,
        provider=Provider.STRIPE,
        provider_session_id=data["id"],
        mode=mode,
        status=data.get("status", "open"),
        url=data.get("url", ""),
        metadata=data.get("metadata") or metadata,
    )


def create_portal_session(request) -> str:
    customer = BillingCustomer.objects.get(
        tenant=request.tenant,
        provider=Provider.STRIPE,
    )
    if not customer.provider_customer_id:
        raise ValueError("Stripe billing customer does not have a Stripe customer ID.")
    data = _stripe_dict(
        _stripe_client().v1.billing_portal.sessions.create(
            {
                "customer": customer.provider_customer_id,
                "return_url": request.build_absolute_uri(reverse("billing:dashboard")),
            },
        ),
    )
    return str(data["url"])


def cancel_subscription(
    subscription: Subscription,
    at_period_end: bool = True,
) -> Subscription:
    if subscription.provider != Provider.STRIPE:
        raise ValueError("This subscription is not managed by Stripe.")
    data = _stripe_dict(
        _stripe_client().v1.subscriptions.update(
            subscription.provider_subscription_id,
            {"cancel_at_period_end": at_period_end},
        ),
    )
    return sync_subscription(data)


def change_subscription(
    subscription: Subscription,
    price: Price,
) -> Subscription:
    if subscription.provider != Provider.STRIPE:
        raise ValueError("This subscription is not managed by Stripe.")
    if not price.provider_price_id:
        raise ValueError("The target price has not been synchronized to Stripe.")
    remote = _stripe_client().v1.subscriptions.retrieve(
        subscription.provider_subscription_id,
    )
    if not remote.items.data:
        raise ValueError("Stripe subscription has no subscription items.")
    data = _stripe_dict(
        _stripe_client().v1.subscriptions.update(
            subscription.provider_subscription_id,
            {
                "items": [
                    {
                        "id": remote.items.data[0].id,
                        "price": price.provider_price_id,
                    },
                ],
            },
        ),
    )
    return sync_subscription(data)


def sync_subscription(data: dict[str, Any]) -> Subscription:
    customer_id = str(data.get("customer") or "")
    customer = BillingCustomer.objects.select_related("tenant").get(
        provider=Provider.STRIPE,
        provider_customer_id=customer_id,
    )
    items = data.get("items", {}).get("data", [])
    if not items:
        raise ValueError("Stripe subscription has no price item.")
    price = Price.objects.filter(
        provider_price_id=str((items[0].get("price") or {}).get("id") or ""),
    ).first()
    if not price:
        raise ValueError("No local billing price for the Stripe price.")
    subscription, _ = Subscription.objects.get_or_create(
        provider=Provider.STRIPE,
        provider_subscription_id=data["id"],
        defaults={
            "tenant": customer.tenant,
            "price": price,
            "status": data.get("status", Subscription.Status.INCOMPLETE),
            "provider_customer_id": customer_id,
        },
    )
    subscription.tenant = customer.tenant
    subscription.price = price
    subscription.status = data.get("status", subscription.status)
    subscription.provider_customer_id = customer_id
    subscription.current_period_start = _dt(data.get("current_period_start"))
    subscription.current_period_end = _dt(data.get("current_period_end"))
    subscription.cancel_at_period_end = bool(data.get("cancel_at_period_end", False))
    subscription.canceled_at = _dt(data.get("canceled_at"))
    subscription.trial_end = _dt(data.get("trial_end"))
    subscription.metadata = data.get("metadata") or {}
    subscription.save()
    return subscription


def sync_invoice(data: dict[str, Any]) -> Invoice:
    customer_id = str(data.get("customer") or "")
    customer = BillingCustomer.objects.select_related("tenant").get(
        provider=Provider.STRIPE,
        provider_customer_id=customer_id,
    )
    subscription = Subscription.objects.filter(
        provider=Provider.STRIPE,
        provider_subscription_id=data.get("subscription", ""),
    ).first()
    invoice, _ = Invoice.objects.get_or_create(
        provider=Provider.STRIPE,
        provider_invoice_id=data["id"],
        defaults={
            "tenant": customer.tenant,
            "subscription": subscription,
            "status": data.get("status") or Invoice.Status.DRAFT,
        },
    )
    invoice.tenant = customer.tenant
    invoice.subscription = subscription
    invoice.number = data.get("number") or ""
    invoice.status = data.get("status") or invoice.status
    invoice.amount_due = int(data.get("amount_due") or 0)
    invoice.amount_paid = int(data.get("amount_paid") or 0)
    invoice.currency = str(data.get("currency") or invoice.currency).upper()
    invoice.hosted_invoice_url = data.get("hosted_invoice_url") or ""
    invoice.invoice_pdf = data.get("invoice_pdf") or ""
    invoice.period_start = _dt(data.get("period_start"))
    invoice.period_end = _dt(data.get("period_end"))
    if invoice.status == Invoice.Status.PAID and not invoice.paid_at:
        invoice.paid_at = timezone.now()
    invoice.metadata = data.get("metadata") or {}
    invoice.save()
    return invoice


def _price_from_event(
    data: dict[str, Any],
    *,
    session_id: str = "",
) -> Price | None:
    metadata = data.get("metadata") or {}
    if metadata.get("price_id"):
        price = Price.objects.filter(pk=metadata["price_id"]).first()
        if price:
            return price
    if session_id:
        session = (
            CheckoutSession.objects.filter(
                provider=Provider.STRIPE,
                provider_session_id=session_id,
            )
            .select_related("price")
            .first()
        )
        return session.price if session else None
    return None


def sync_payment_intent(data: dict[str, Any]) -> Payment | None:
    payment_id = str(data.get("id") or "")
    if not payment_id:
        return None
    customer_id = str(data.get("customer") or "")
    metadata = data.get("metadata") or {}
    customer = (
        BillingCustomer.objects.filter(
            provider=Provider.STRIPE,
            provider_customer_id=customer_id,
        )
        .select_related("tenant")
        .first()
    )
    if not customer and metadata.get("tenant_id"):
        customer = (
            BillingCustomer.objects.filter(
                tenant_id=metadata["tenant_id"],
                provider=Provider.STRIPE,
            )
            .select_related("tenant")
            .first()
        )
    if not customer:
        return None
    subscription = (
        Subscription.objects.filter(
            provider=Provider.STRIPE,
            provider_customer_id=customer_id,
            status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
        )
        .order_by("-created_at")
        .first()
    payment, _ = Payment.objects.get_or_create(
        provider=Provider.STRIPE,
        provider_payment_id=payment_id,
        defaults={
            "tenant": customer.tenant,
            "amount": int(data.get("amount_received") or data.get("amount") or 0),
            "currency": str(data.get("currency") or "usd").upper(),
            "status": Payment.Status.PENDING,
        },
    )
    payment.tenant = customer.tenant
    payment.subscription = subscription
    payment.amount = int(
        data.get("amount_received") or data.get("amount") or payment.amount,
    )
    payment.currency = str(data.get("currency") or payment.currency).upper()
    payment.status = (
        Payment.Status.SUCCEEDED
        if data.get("status") == "succeeded"
        else Payment.Status.FAILED
        if data.get("status") in {"requires_payment_method", "canceled"}
        else Payment.Status.PENDING
    )
    if payment.status == Payment.Status.SUCCEEDED and not payment.paid_at:
        payment.paid_at = timezone.now()
    payment.metadata = (
        {**payment.metadata, **metadata, "customer_id": customer_id}
        if customer_id
        else {**payment.metadata, **metadata}
    )
    payment.save()
    return payment


def expire_one_time_subscriptions() -> int:
    now = timezone.now()
    return Subscription.objects.filter(
        cancel_at_period_end=True,
        current_period_end__lte=now,
        status__in=[
            Subscription.Status.ACTIVE,
            Subscription.Status.TRIALING,
            Subscription.Status.PAST_DUE,
        ],
    ).update(
        status=Subscription.Status.CANCELED,
        canceled_at=now,
        updated_at=now,
    )


def get_current_subscription(tenant) -> Subscription | None:
    now = timezone.now()
    return (
        Subscription.objects.select_related("price__product")
        .filter(
            tenant=tenant,
            status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
            current_period_end__gt=now,
        )
        .order_by("-created_at")
        .first()
    )


def has_feature(tenant, feature_key: str) -> bool:
    subscription = get_current_subscription(tenant)
    return bool(
        subscription
        and subscription.price.product.product_features.filter(
            feature__key=feature_key,
            feature__active=True,
            enabled=True,
        ).exists()
    )
