"""Payment gateway factory for managing gateway instances"""


from .base import BasePaymentGateway
from .khalti_gateway import KhaltiGateway
from .stripe_gateway import StripeGateway


class PaymentGatewayFactory:
    """Factory class for creating payment gateway instances"""

    _gateways: dict[str, type] = {
        "khalti": KhaltiGateway,
        "stripe": StripeGateway,
        # Future gateways can be registered here
        # 'paypal': PayPalGateway,
        # 'razorpay': RazorpayGateway,
    }

    @classmethod
    def get_gateway(cls, name: str) -> BasePaymentGateway:
        """
        Get a payment gateway instance by name

        Args:
            name: Gateway name (e.g., 'khalti', 'stripe')

        Returns:
            Instance of the gateway adapter

        Raises:
            ValueError: If gateway is not registered
        """
        gateway_class = cls._gateways.get(name.lower())
        if not gateway_class:
            raise ValueError(f"Unknown payment gateway: {name}")

        return gateway_class()

    @classmethod
    def register_gateway(cls, name: str, gateway_class: type[BasePaymentGateway]):
        """
        Register a new payment gateway

        Args:
            name: Gateway name
            gateway_class: Gateway class (must inherit from BasePaymentGateway)
        """
        cls._gateways[name.lower()] = gateway_class

    @classmethod
    def get_available_gateways(cls) -> list:
        """Get list of registered gateway names"""
        return list(cls._gateways.keys())
