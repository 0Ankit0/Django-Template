from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.admin import TabularInline

from .models import BillingCustomer, CheckoutSession, Feature, Invoice, Payment, Price, Product, ProductFeature, ProviderConfiguration, Subscription, WebhookEvent


class PriceInline(TabularInline):
    model = Price
    extra = 0
    fields = ["nickname", "amount", "currency", "interval", "interval_count", "active", "stripe_price_id"]
    readonly_fields = ["stripe_price_id"]


class ProductFeatureInline(TabularInline):
    model = ProductFeature
    extra = 0


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ["name", "slug", "active", "created_at"]
    list_filter = ["active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [PriceInline, ProductFeatureInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Price)
class PriceAdmin(ModelAdmin):
    list_display = ["product", "nickname", "amount", "currency", "interval", "interval_count", "active", "stripe_price_id"]
    list_filter = ["active", "interval", "currency"]
    search_fields = ["product__name", "nickname", "stripe_price_id"]
    readonly_fields = ["stripe_price_id", "created_at"]


@admin.register(Feature)
class FeatureAdmin(ModelAdmin):
    list_display = ["name", "key", "active"]
    list_filter = ["active"]
    search_fields = ["name", "key"]


@admin.register(ProductFeature)
class ProductFeatureAdmin(ModelAdmin):
    list_display = ["product", "feature", "enabled"]
    list_filter = ["enabled", "feature"]
    search_fields = ["product__name", "feature__name", "feature__key"]


@admin.register(ProviderConfiguration)
class ProviderConfigurationAdmin(ModelAdmin):
    list_display = ["provider", "environment", "enabled", "updated_at"]
    list_filter = ["provider", "environment", "enabled"]
    search_fields = ["provider", "notes"]
    readonly_fields = ["updated_at"]
    fieldsets = ((None, {"fields": ("provider", "enabled", "environment", "notes", "updated_at")}), ("Credentials", {"description": "Provider secrets are configured through environment variables. Never paste secret API keys into Django Admin."}))


@admin.register(BillingCustomer)
class BillingCustomerAdmin(ModelAdmin):
    list_display = ["tenant", "provider", "email", "name", "provider_customer_id", "updated_at"]
    list_filter = ["provider"]
    search_fields = ["tenant__name", "email", "name", "provider_customer_id"]
    readonly_fields = ["provider_customer_id", "created_at", "updated_at"]


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ["tenant", "price", "provider", "status", "current_period_end", "cancel_at_period_end", "provider_subscription_id"]
    list_filter = ["provider", "status", "cancel_at_period_end", "price__product"]
    search_fields = ["tenant__name", "provider_subscription_id", "provider_customer_id"]
    readonly_fields = ["provider_subscription_id", "created_at", "updated_at"]


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ["tenant", "amount", "currency", "provider", "status", "paid_at", "provider_payment_id"]
    list_filter = ["provider", "status", "currency"]
    search_fields = ["tenant__name", "provider_payment_id", "provider_invoice_id"]
    readonly_fields = ["provider_payment_id", "created_at", "updated_at"]


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = ["tenant", "provider", "number", "status", "amount_due", "amount_paid", "currency", "created_at"]
    list_filter = ["provider", "status", "currency"]
    search_fields = ["tenant__name", "number", "provider_invoice_id"]
    readonly_fields = ["provider_invoice_id", "created_at", "updated_at"]


@admin.register(CheckoutSession)
class CheckoutSessionAdmin(ModelAdmin):
    list_display = ["tenant", "price", "provider", "mode", "status", "created_at", "completed_at"]
    list_filter = ["provider", "mode", "status"]
    search_fields = ["tenant__name", "provider_session_id"]
    readonly_fields = ["provider_session_id", "created_at"]


@admin.register(WebhookEvent)
class WebhookEventAdmin(ModelAdmin):
    list_display = ["provider", "event_type", "event_id", "processed", "processing", "created_at", "processed_at"]
    list_filter = ["provider", "processed", "processing", "event_type"]
    search_fields = ["event_id", "event_type"]
    readonly_fields = ["provider", "event_id", "event_type", "payload", "processed", "processing", "processed_at", "error", "created_at"]
