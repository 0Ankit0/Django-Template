from typing import Any

from django.db import transaction

from .models import BillingCustomer
from .models import CheckoutSession
from .models import Price
from .models import Provider
from .services import _stripe_client
from .services import _stripe_dict


@transaction.atomic
def create_or_get_customer(tenant, email: str = "", name: str = "") -> BillingCustomer:
    customer = BillingCustomer.objects.filter(tenant=tenant, provider=Provider.STRIPE).first()
    if customer and customer.provider_customer_id:
        changed = False
        if email and customer.email != email:
            customer.email = email
            changed = True
        if name and customer.name != name:
            customer.name = name
            changed = True
        if changed:
            customer.save(update_fields=["email", "name", "updated_at"])
        return customer

    stripe_customer = _stripe_client().v1.customers.create(
        {"email": email or None, "name": name or None, "metadata": {"tenant_id": str(tenant.pk)}}
    )
    return BillingCustomer.objects.create(
        tenant=tenant,
        provider=Provider.STRIPE,
        provider_customer_id=str(stripe_customer.id),
        email=email,
        name=name,
    )


def create_checkout_session(request, price: Price) -> CheckoutSession:
    if not price.stripe_price_id:
        raise ValueError("This price has not been synchronized to Stripe yet.")
    tenant = request.tenant
    customer = create_or_get_customer(
        tenant,
        email=getattr(request.user, "email", ""),
        name=getattr(request.user, "name", "") or str(request.user),
    )
    mode = "subscription" if price.is_recurring else "payment"
    success_url = request.build_absolute_uri("/billing/success/") + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = request.build_absolute_uri("/billing/pricing/")
    metadata = {"tenant_id": str(tenant.pk), "price_id": str(price.pk)}
    payload: dict[str, Any] = {
        "mode": mode,
        "customer": customer.provider_customer_id,
        "line_items": [{"price": price.stripe_price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(tenant.pk),
        "metadata": metadata,
    }
    if price.is_recurring:
        payload["subscription_data"] = {"metadata": metadata}
    else:
        payload["payment_intent_data"] = {"metadata": metadata}

    stripe_session = _stripe_client().v1.checkout.sessions.create(payload)
    data = _stripe_dict(stripe_session)
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
