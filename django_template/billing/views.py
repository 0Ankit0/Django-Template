import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from .checkout import create_checkout_session
from .models import Price
from .services import cancel_subscription
from .services import create_portal_session
from .services import get_current_subscription
from .services import handle_webhook


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
        {"prices": prices, "subscription": get_current_subscription(request.tenant)},
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
    if price.is_recurring and get_current_subscription(request.tenant):
        messages.info(request, "Your tenant already has an active subscription. Use the billing portal to change it.")
        return redirect("billing:dashboard")
    if not price.provider_price_id:
        messages.error(request, "This price has not been synchronized to Stripe yet.")
        return redirect("billing:pricing")
    session = create_checkout_session(request, price)
    return redirect(session.url)


@login_required
@require_POST
def portal(request: HttpRequest) -> HttpResponse:
    try:
        return redirect(create_portal_session(request))
    except Exception as exc:
        messages.error(request, f"Unable to open the billing portal: {exc}")
        return redirect("billing:dashboard")


@login_required
@require_POST
def cancel(request: HttpRequest) -> HttpResponse:
    subscription = get_current_subscription(request.tenant)
    if not subscription:
        messages.info(request, "There is no active subscription to cancel.")
        return redirect("billing:dashboard")
    try:
        cancel_subscription(subscription, at_period_end=True)
        messages.success(request, "Your subscription will cancel at the end of the current billing period.")
    except Exception as exc:
        messages.error(request, f"Unable to cancel the subscription: {exc}")
    return redirect("billing:dashboard")


@login_required
@require_GET
def success(request: HttpRequest) -> HttpResponse:
    session_id = request.GET.get("session_id", "")
    return render(request, "billing/success.html", {"session_id": session_id})


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
