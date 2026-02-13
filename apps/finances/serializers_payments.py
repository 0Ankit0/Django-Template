"""Payment API serializers"""

from django.conf import settings
from rest_framework import serializers

from .models import PaymentTransaction, WebhookEvent


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """Serializer for PaymentTransaction model"""

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "gateway",
            "gateway_transaction_id",
            "amount",
            "currency",
            "status",
            "payment_method",
            "customer_info",
            "gateway_response",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "gateway_transaction_id",
            "status",
            "gateway_response",
            "created_at",
            "updated_at",
        ]


class InitiatePaymentSerializer(serializers.Serializer):
    """Serializer for initiating a payment"""

    gateway = serializers.ChoiceField(
        choices=[("khalti", "Khalti"), ("stripe", "Stripe")], required=True, help_text="Payment gateway to use"
    )
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, help_text="Payment amount (optional, calculated server-side)"
    )
    currency = serializers.CharField(max_length=3, default="NPR", required=False, help_text="Currency code")
    purchase_order_id = serializers.CharField(max_length=255, required=True, help_text="Unique order identifier")
    purchase_order_name = serializers.CharField(
        max_length=255, required=False, help_text="Order description (optional, calculated server-side)"
    )
    customer_name = serializers.CharField(
        max_length=255, required=False, help_text="Customer full name (optional, derived from user)"
    )
    customer_email = serializers.EmailField(required=False, help_text="Customer email (optional, derived from user)")
    customer_phone = serializers.CharField(
        max_length=20, required=False, help_text="Customer phone number (optional, derived from user)"
    )
    return_url = serializers.URLField(required=True, help_text="URL to redirect after payment")
    website_url = serializers.URLField(required=False, help_text="Website URL (optional)")
    payment_method_id = serializers.CharField(required=False, help_text="ID of saved payment method to use")

    def validate_gateway(self, value):
        """Validate that the gateway is enabled"""
        enabled_gateways = settings.ENABLED_PAYMENT_GATEWAYS
        if value not in enabled_gateways:
            raise serializers.ValidationError(
                f"Gateway '{value}' is not enabled. Available gateways: {', '.join(enabled_gateways)}"
            )
        return value


class VerifyPaymentSerializer(serializers.Serializer):
    """Serializer for verifying a payment"""

    transaction_id = serializers.UUIDField(required=True, help_text="Payment transaction ID")


class PaymentConfigSerializer(serializers.Serializer):
    """Serializer for payment gateway configuration"""

    gateways = serializers.DictField(help_text="Available payment gateways and their configuration")
    enabled_gateways = serializers.ListField(child=serializers.CharField(), help_text="List of enabled gateway names")


class WebhookEventSerializer(serializers.ModelSerializer):
    """Serializer for WebhookEvent model"""

    class Meta:
        model = WebhookEvent
        fields = [
            "id",
            "gateway",
            "event_type",
            "payload",
            "processed",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields
