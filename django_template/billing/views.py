import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .checkout import create_checkout_session
from .models import CheckoutSession
from .models import Payment
from .models import Price
from .models import Provider
from .models import ProviderConfiguration
from .models import WebhookEvent
from .providers import create_esewa_checkout
from .providers import create_khalti_checkout
from .providers import esewa_status
from .providers import khalti_lookup
from .providers import verify_esewa_response
from .services import cancel_subscription
from .services import create_or_update_one_time_subscription
from .services import create_portal_session
from .services import get_current_subscription
from .services import handle_webhook


def provider_enabled(provider: str) -> bool:
    config = ProviderConfiguration.objects.filter(provider=provider).first()
    if config is not None:
        return config.enabled
    return bool(getattr(settings, f"BILLING_{provider.upper()}_ENABLED", True))


def enabled_providers(price: Price) -> list[tuple[str, str]]:
    providers = []
    if provider_enabled(Provider.STRIPE):
        providers.append((Provider.STRIPE, "Stripe"))
    if provider_enabled(Provider.KHALTI) and price.currency.lower() == "npr" and price.is_one_time:
        providers.append((Provider.KHALTI, "Khalti"))
    if provider_enabled(Provider.ESEWA) and price.currency.lower() == "npr" and price.is_one_time:
        providers.append((Provider.ESEWA, "eSewa"))
    return providers


@login_required
def pricing(request: HttpRequest) -> HttpResponse:
    prices = (
        Price.objects.select_related("product")
        .prefetch_related("product__product_features__feature")
        .filter(active=True, product__active=True)
        .order_by("product__name", "amount")
    )
    return render(
        request,
        "billing/pricing.html",
        {
            "cards": [(price, enabled_providers(price)) for price in prices],
            "subscription": get_current_subscription(request.tenant),
        },
    )


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    subscription = get_current_subscription(request.tenant)
    payments = request.tenant.payments.select_related("subscription__price__product")[:10]
    invoices = request.tenant.billing_invoices.select_related("subscription__price__product")[:10]
    return render(
        request,
        "billing/dashboard.html",
        {"subscription": subscription, "payments": payments, "invoices": invoices},
    )


@login_required
@require_POST
def checkout(request: HttpRequest, price_id: int) -> HttpResponse:
    price = get_object_or_404(Price, pk=price_id, active=True, product__active=True)
    provider = request.POST.get("provider", Provider.STRIPE)
    if provider not in dict(enabled_providers(price)):
        messages.error(request, "That payment provider is not available for this price.")
        return redirect("billing:pricing")
    if price.is_recurring and get_current_subscription(request.tenant):
        messages.info(
            request,
            "Your tenant already has an active subscription. Use the billing portal to manage it.",
        )
        return redirect("billing:dashboard")
    try:
        if provider == Provider.STRIPE:
            return redirect(create_checkout_session(request, price).url)
        if provider == Provider.KHALTI:
            result = create_khalti_checkout(request, price)
            CheckoutSession.objects.create(
                tenant=request.tenant,
                price=price,
                provider=provider,
                provider_session_id=result.reference,
                mode="payment",
                url=result.redirect_url,
                metadata={"provider": provider, **(result.metadata or {})},
            )
            return redirect(result.redirect_url)
        result = create_esewa_checkout(request, price)
        CheckoutSession.objects.create(
            tenant=request.tenant,
            price=price,
            provider=provider,
            provider_session_id=result.reference,
            mode="payment",
            metadata={"provider": provider, **(result.metadata or {})},
        )
        return render(
            request,
            "billing/esewa_redirect.html",
            {"action": result.form_action, "fields": result.form_fields, "provider": provider},
        )
    except Exception as exc:
        messages.error(request, f"Unable to start payment: {exc}")
        return redirect("billing:pricing")


@login_required
@require_POST
def portal(request: HttpRequest) -> HttpResponse:
    try:
        return redirect(create_portal_session(request))
    except Exception as exc:
        messages.error(request, f"Unable to open the Stripe billing portal: {exc}")
        return redirect("billing:dashboard")


@login_required
@require_POST
def cancel(request: HttpRequest) -> HttpResponse:
    subscription = get_current_subscription(request.tenant)
    if not subscription:
        messages.info(request, "There is no active subscription to cancel.")
    elif subscription.provider != Provider.STRIPE:
        messages.info(request, "Local-wallet purchases expire automatically at their Price interval.")
    else:
        try:
            cancel_subscription(subscription, at_period_end=True)
            messages.success(request, "Your subscription will cancel at the end of the current billing period.")
        except Exception as exc:
            messages.error(request, f"Unable to cancel the subscription: {exc}")
    return redirect("billing:dashboard")


@login_required
@require_GET
def success(request: HttpRequest) -> HttpResponse:
    provider = request.GET.get("provider", Provider.STRIPE)
    session_id = request.GET.get("session_id", "")
    session = None
    payment = None
    subscription = None
    if session_id:
        session = (
            CheckoutSession.objects.filter(
                provider=Provider.STRIPE,
                provider_session_id=session_id,
            )
            .select_related("price")
            .first()
        )
        if session:
            payment_intent = session.metadata.get("payment_intent")
            if payment_intent:
                payment = (
                    Payment.objects.filter(
                        provider=Provider.STRIPE,
                        provider_payment_id=payment_intent,
                    )
                    .select_related("subscription")
                    .first()
                )
            subscription = payment.subscription if payment else None
    return render(
        request,
        "billing/success.html",
        {
            "provider": provider,
            "session_id": session_id,
            "session": session,
            "payment": payment,
            "subscription": subscription,
        },
    )


@login_required
@require_GET
def cancelled(request: HttpRequest) -> HttpResponse:
    provider = request.GET.get("provider", Provider.STRIPE)
    return render(request, "billing/cancel.html", {"provider": provider})


def _record_provider_event(provider: str, event_id: str, event_type: str, payload: dict) -> WebhookEvent:
    event, _ = WebhookEvent.objects.get_or_create(
        provider=provider,
        event_id=event_id,
        defaults={"event_type": event_type, "payload": payload},
    )
    return event


@csrf_exempt
@require_GET
def khalti_callback(request: HttpRequest) -> HttpResponse:
    pidx = request.GET.get("pidx", "")
    session = get_object_or_404(
        CheckoutSession,
        provider=Provider.KHALTI,
        provider_session_id=pidx,
    )
    result = khalti_lookup(pidx)
    webhook = _record_provider_event(
        Provider.KHALTI,
        pidx,
        "payment.completed",
        {"query": request.GET.dict(), "lookup": result},
    )
    if result.get("purchase_order_id") != session.metadata.get("purchase_order_id"):
        webhook.error = "Khalti order mismatch"
        webhook.save(update_fields=["error"])
        return redirect(f"{request.build_absolute_uri('/billing/cancelled/')}?provider=khalti")
    verified = (
        result.get("status") == "Completed"
        and int(result.get("total_amount") or 0) == session.price.amount
    )
    payment, _ = Payment.objects.update_or_create(
        provider=Provider.KHALTI,
        provider_payment_id=str(result.get("transaction_id") or pidx),
        defaults={
            "tenant": session.tenant,
            "amount": session.price.amount,
            "currency": "npr",
            "status": Payment.Status.SUCCEEDED if verified else Payment.Status.FAILED,
            "paid_at": timezone.now() if verified else None,
            "metadata": {"pidx": pidx, "status": result.get("status")},
        },
    )
    webhook.processed = True
    webhook.processed_at = timezone.now()
    if verified:
        session.status = "complete"
        session.completed_at = timezone.now()
        session.save(update_fields=["status", "completed_at"])
        create_or_update_one_time_subscription(payment, session.price, provider_reference=pidx)
        webhook.save(update_fields=["processed", "processed_at"])
        return redirect(f"{request.build_absolute_uri('/billing/success/')}?provider=khalti")
    webhook.error = f"Khalti payment failed: {result.get('status', 'Unknown status')}"
    webhook.save(update_fields=["processed", "processed_at", "error"])
    return redirect(f"{request.build_absolute_uri('/billing/cancelled/')}?provider=khalti")


@csrf_exempt
@require_GET
def esewa_callback(request: HttpRequest) -> HttpResponse:
    encoded = request.GET.get("data", "")
    if not encoded:
        return redirect(f"{request.build_absolute_uri('/billing/cancelled/')}?provider=esewa")
    try:
        data = verify_esewa_response(encoded)
        session = get_object_or_404(
            CheckoutSession,
            provider=Provider.ESEWA,
            provider_session_id=data["transaction_uuid"],
        )
        webhook = _record_provider_event(
            Provider.ESEWA,
            data["transaction_uuid"],
            "payment.completed",
            {"query": request.GET.dict(), "verified_response": data},
        )
        expected = f"{session.price.amount / 100:.2f}"
        verified = (
            data.get("status") == "COMPLETE"
            and data.get("product_code") == session.metadata.get("product_code")
            and Decimal(str(data.get("total_amount"))) == Decimal(expected)
        )
        if verified:
            verified = esewa_status(
                data["transaction_uuid"],
                expected,
            ).get("status") == "COMPLETE"
        payment, _ = Payment.objects.update_or_create(
            provider=Provider.ESEWA,
            provider_payment_id=str(
                data.get("transaction_code") or data["transaction_uuid"]
            ),
            defaults={
                "tenant": session.tenant,
                "amount": session.price.amount,
                "currency": "npr",
                "status": Payment.Status.SUCCEEDED if verified else Payment.Status.FAILED,
                "paid_at": timezone.now() if verified else None,
                "metadata": data,
            },
        )
        webhook.processed = True
        webhook.processed_at = timezone.now()
        if verified:
            session.status = "complete"
            session.completed_at = timezone.now()
            session.save(update_fields=["status", "completed_at"])
            create_or_update_one_time_subscription(
                payment,
                session.price,
                provider_reference=data["transaction_uuid"],
            )
            webhook.save(update_fields=["processed", "processed_at"])
            return redirect(f"{request.build_absolute_uri('/billing/success/')}?provider=esewa")
        webhook.error = "eSewa payment could not be verified"
        webhook.save(update_fields=["processed", "processed_at", "error"])
    except Exception:
        pass
    return redirect(f"{request.build_absolute_uri('/billing/cancelled/')}?provider=esewa")


@csrf_exempt
@require_POST
def webhook(request: HttpRequest) -> HttpResponse:
    try:
        handle_webhook(request.body, request.headers.get("Stripe-Signature", ""))
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({"detail": "Invalid webhook."}, status=400)
    except Exception:
        return JsonResponse({"detail": "Webhook processing failed."}, status=500)
    return JsonResponse({"received": True})
