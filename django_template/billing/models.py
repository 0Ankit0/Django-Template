from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Product(models.Model):
    name = models.CharField(_("Name"), max_length=255)
    slug = models.SlugField(_("Slug"), unique=True)
    description = models.TextField(_("Description"), blank=True)
    active = models.BooleanField(_("Active"), default=True)
    provider = models.CharField(max_length=32, default="stripe", editable=False)
    provider_product_id = models.CharField(max_length=255, blank=True, editable=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Price(models.Model):
    class Interval(models.TextChoices):
        ONE_TIME = "one_time", _("One time")
        MONTH = "month", _("Monthly")
        YEAR = "year", _("Yearly")

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="prices")
    nickname = models.CharField(max_length=255, blank=True)
    amount = models.PositiveBigIntegerField(
        validators=[MinValueValidator(0)],
        help_text=_("Amount in the smallest currency unit, e.g. cents."),
    )
    currency = models.CharField(max_length=3, default="usd")
    interval = models.CharField(max_length=20, choices=Interval.choices, default=Interval.MONTH)
    interval_count = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    provider = models.CharField(max_length=32, default="stripe", editable=False)
    provider_price_id = models.CharField(max_length=255, blank=True, editable=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["product__name", "amount"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(interval_count__gte=1),
                name="billing_price_interval_count_positive",
            ),
        ]

    @property
    def is_recurring(self) -> bool:
        return self.interval != self.Interval.ONE_TIME

    @property
    def amount_decimal(self) -> Decimal:
        return Decimal(self.amount) / Decimal("100")

    def __str__(self) -> str:
        suffix = "" if self.interval == self.Interval.ONE_TIME else f" / {self.interval}"
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
        constraints = [
            models.UniqueConstraint(fields=["product", "feature"], name="billing_product_feature_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.product}: {self.feature}"


class BillingCustomer(models.Model):
    tenant = models.OneToOneField(
        "tenants.Tenant",
        on_delete=models.PROTECT,
        related_name="billing_customer",
    )
    provider = models.CharField(max_length=32, default="stripe", editable=False)
    provider_customer_id = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True)
    name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name or self.email or str(self.tenant)


class Subscription(models.Model):
    class Status(models.TextChoices):
        INCOMPLETE = "incomplete", _("Incomplete")
        INCOMPLETE_EXPIRED = "incomplete_expired", _("Incomplete expired")
        TRIALING = "trialing", _("Trialing")
        ACTIVE = "active", _("Active")
        PAST_DUE = "past_due", _("Past due")
        CANCELED = "canceled", _("Canceled")
        UNPAID = "unpaid", _("Unpaid")
        PAUSED = "paused", _("Paused")

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.PROTECT, related_name="subscriptions")
    price = models.ForeignKey(Price, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=32, choices=Status.choices)
    provider = models.CharField(max_length=32, default="stripe", editable=False)
    provider_subscription_id = models.CharField(max_length=255, unique=True)
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
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["provider_customer_id"]),
        ]

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
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    amount = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=32, choices=Status.choices)
    provider = models.CharField(max_length=32, default="stripe", editable=False)
    provider_payment_id = models.CharField(max_length=255, unique=True)
    provider_invoice_id = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
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
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    provider_invoice_id = models.CharField(max_length=255, unique=True)
    number = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices)
    amount_due = models.PositiveBigIntegerField(default=0)
    amount_paid = models.PositiveBigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="usd")
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

    def __str__(self) -> str:
        return self.number or self.provider_invoice_id


class CheckoutSession(models.Model):
    class Mode(models.TextChoices):
        PAYMENT = "payment", _("Payment")
        SUBSCRIPTION = "subscription", _("Subscription")

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.PROTECT, related_name="checkout_sessions")
    price = models.ForeignKey(Price, on_delete=models.PROTECT, related_name="checkout_sessions")
    provider_session_id = models.CharField(max_length=255, unique=True)
    mode = models.CharField(max_length=32, choices=Mode.choices)
    status = models.CharField(max_length=32, default="open")
    url = models.URLField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.provider_session_id


class WebhookEvent(models.Model):
    provider = models.CharField(max_length=32, default="stripe")
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=255)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["event_type", "processed"])]

    def __str__(self) -> str:
        return f"{self.event_type}: {self.event_id}"
