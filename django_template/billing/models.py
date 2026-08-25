from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Provider(models.TextChoices):
    STRIPE = "stripe", _("Stripe")
    KHALTI = "khalti", _("Khalti")
    ESEWA = "esewa", _("eSewa")


class Product(models.Model):
    name = models.CharField(_("Name"), max_length=255)
    slug = models.SlugField(_("Slug"), unique=True)
    description = models.TextField(_("Description"), blank=True)
    active = models.BooleanField(_("Active"), default=True)
    stripe_product_id = models.CharField(max_length=255, blank=True, editable=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Price(models.Model):
    class Interval(models.TextChoices):
        DAY = "day", _("Days")
        WEEK = "week", _("Weeks")
        MONTH = "month", _("Months")
        YEAR = "year", _("Years")

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="prices")
    nickname = models.CharField(max_length=255, blank=True)
    amount = models.PositiveBigIntegerField(validators=[MinValueValidator(0)], help_text=_("Amount in the smallest currency unit."))
    currency = models.CharField(max_length=3, default="npr")
    interval = models.CharField(max_length=20, choices=Interval.choices, default=Interval.MONTH)
    interval_count = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    stripe_price_id = models.CharField(max_length=255, blank=True, editable=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["product__name", "amount"]
        constraints = [models.CheckConstraint(condition=models.Q(interval_count__gte=1), name="billing_price_interval_count_positive")]

    @property
    def is_one_time(self) -> bool:
        return bool(self.metadata.get("one_time", False))

    @property
    def is_recurring(self) -> bool:
        return not self.is_one_time

    @property
    def amount_decimal(self) -> Decimal:
        return Decimal(self.amount) / Decimal("100")

    def __str__(self) -> str:
        suffix = "" if self.is_one_time else f" / {self.interval_count} {self.interval}"
        return f"{self.product.name} - {self.amount_decimal:.2f} {self.currency.upper()}{suffix}"


class Feature(models.Model):
    key = models.SlugField(unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProductFeature(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_features")
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, related_name="product_features")
    enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "feature"], name="billing_product_feature_unique")]

    def __str__(self) -> str:
        return f"{self.product}: {self.feature}"


class ProviderConfiguration(models.Model):
    class Environment(models.TextChoices):
        SANDBOX = "sandbox", _("Sandbox / Test")
        LIVE = "live", _("Live / Production")

    provider = models.CharField(max_length=32, choices=Provider.choices, unique=True)
    enabled = models.BooleanField(default=True)
    environment = models.CharField(max_length=16, choices=Environment.choices, default=Environment.SANDBOX)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider"]

    def __str__(self) -> str:
        return self.get_provider_display()


class BillingCustomer(models.Model):
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.PROTECT, related_name="billing_customers")
    provider = models.CharField(max_length=32, choices=Provider.choices)
    provider_customer_id = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "provider"], name="billing_customer_tenant_provider_unique"), models.UniqueConstraint(fields=["provider", "provider_customer_id"], name="billing_customer_provider_id_unique")]

    def __str__(self) -> str:
        return self.name or self.email or str(self.tenant)


class Subscription(models.Model):
    class Status(models.TextChoices):
        INCOMPLETE = "incomplete", _("Incomplete")
        TRIALING = "trialing", _("Trialing")
        ACTIVE = "active", _("Active")
        PAST_DUE = "past_due", _("Past due")
        CANCELED = "canceled", _("Canceled")
        UNPAID = "unpaid", _("Unpaid")
        PAUSED = "paused", _("Paused")

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.PROTECT, related_name="subscriptions")
    price = models.ForeignKey(Price, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=32, choices=Status.choices)
    provider = models.CharField(max_length=32, choices=Provider.choices)
    provider_subscription_id = models.CharField(max_length=255)
    provider_customer_id = models.CharField(max_length=255, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "provider_subscription_id"], name="billing_subscription_provider_id_unique")]
        indexes = [models.Index(fields=["tenant", "status"]), models.Index(fields=["provider", "provider_customer_id"])]

    def __str__(self) -> str:
        return f"{self.tenant} - {self.price.product} ({self.status})"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCEEDED = "succeeded", _("Succeeded")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")
        PARTIALLY_REFUNDED = "partially_refunded", _("Partially refunded")

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.PROTECT, related_name="payments")
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    amount = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=32, choices=Status.choices)
    provider = models.CharField(max_length=32, choices=Provider.choices)
    provider_payment_id = models.CharField(max_length=255)
    provider_invoice_id = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "provider_payment_id"], name="billing_payment_provider_id_unique")]
        indexes = [models.Index(fields=["tenant", "status"])]

    def __str__(self) -> str:
        return f"{self.amount / 100:.2f} {self.currency.upper()} - {self.status}"


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        OPEN = "open", _("Open")
        PAID = "paid", _("Paid")
        VOID = "void", _("Void")
        UNCOLLECTIBLE = "uncollectible", _("Uncollectible")

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.PROTECT, related_name="billing_invoices")
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    provider = models.CharField(max_length=32, choices=Provider.choices)
    provider_invoice_id = models.CharField(max_length=255)
    number = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices)
    amount_due = models.PositiveBigIntegerField(default=0)
    amount_paid = models.PositiveBigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="npr")
    hosted_invoice_url = models.URLField(blank=True)
    invoice_pdf = models.URLField(blank=True)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "provider_invoice_id"], name="billing_invoice_provider_id_unique")]

    def __str__(self) -> str:
        return self.number or self.provider_invoice_id


class CheckoutSession(models.Model):
    class Mode(models.TextChoices):
        PAYMENT = "payment", _("Payment")
        SUBSCRIPTION = "subscription", _("Subscription")

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.PROTECT, related_name="checkout_sessions")
    price = models.ForeignKey(Price, on_delete=models.PROTECT, related_name="checkout_sessions")
    provider = models.CharField(max_length=32, choices=Provider.choices)
    provider_session_id = models.CharField(max_length=255)
    mode = models.CharField(max_length=32)
    status = models.CharField(max_length=32, default="open")
    url = models.URLField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "provider_session_id"], name="billing_checkout_provider_id_unique")]

    def __str__(self) -> str:
        return self.provider_session_id


class WebhookEvent(models.Model):
    provider = models.CharField(max_length=32, choices=Provider.choices)
    event_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=255)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    processing = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="billing_webhook_provider_event_unique")]
        indexes = [models.Index(fields=["event_type", "processed"])]

    def __str__(self) -> str:
        return f"{self.provider}: {self.event_type}: {self.event_id}"
