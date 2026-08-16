from typing import Any

from django.db import transaction

from .models import BillingCustomer
from .models import CheckoutSession
from .models import Price
from .models import Provider
from .services import _stripe_request


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
    stripe_customer = _stripe_request("/customers", {"email": email, "name": name, "metadata": {"tenant_id": str(tenant.pk)}})
    return BillingCustomer.objects.create(
        tenant=tenant,
        provider=Provider.STRIPE,
        provider_customer_id=stripe_customer["id"],
        email=email,
        name=name,
    )


def create_checkout_session(request, price: Price) -> CheckoutSession:
    tenant = request.tenant
    customer = create_or_get_customer(tenant, email=getattr(request.user, "email", ""), name=getattr(request.user, "name", "") or str(request.user))
    mode = "subscription" if price.is_recurring else "payment"
    success_url = request.build_absolute_uri("/billing/success/") + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = request.build_absolute_uri("/billing/pricing/")
    payload: dict[str, Any] = {
        "mode": mode,
        "customer": customer.provider_customer_id,
        "line_items": [{"price": price.stripe_price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(tenant.pk),
        "metadata": {"tenant_id": str(tenant.pk), "price_id": str(price.pk)},
    }
    if price.is_recurring:
        payload["subscription_data"] = {"metadata": {"tenant_id": str(tenant.pk), "price_id": str(price.pk)}}
    stripe_session = _stripe_request("/checkout/sessions", payload)
    return CheckoutSession.objects.create(
        tenant=tenant,
        price=price,
        provider=Provider.STRIPE,
        provider_session_id=stripe_session["id"],
        mode=mode,
        status=stripe_session.get("status", "open"),
        url=stripe_session.get("url", ""),
        metadata=stripe_session.get("metadata") or {},
    )
