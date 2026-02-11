"""Base payment gateway interface"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BasePaymentGateway(ABC):
    """Abstract base class for payment gateway adapters"""
    
    @abstractmethod
    def initiate_payment(
        self,
        amount: float,
        currency: str,
        customer_info: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Initiate a payment and return payment URL
        
        Args:
            amount: Payment amount in the currency's standard unit (e.g., NPR, USD)
            currency: Currency code (e.g., 'NPR', 'USD')
            customer_info: Customer details (name, email, phone, etc.)
            metadata: Additional metadata (order_id, order_name, return_url, etc.)
        
        Returns:
            Dict containing:
                - payment_url: URL to redirect user for payment
                - transaction_id: Gateway's transaction identifier
                - Any other gateway-specific data
        
        Raises:
            Exception: If payment initiation fails
        """
        pass
    
    @abstractmethod
    def verify_payment(self, transaction_id: str) -> Dict[str, Any]:
        """
        Verify payment status with the gateway
        
        Args:
            transaction_id: Gateway's transaction identifier
        
        Returns:
            Dict containing:
                - status: Payment status ('completed', 'pending', 'failed', etc.)
                - amount: Payment amount
                - currency: Currency code
                - Any other payment details
        
        Raises:
            Exception: If verification fails
        """
        pass
    
    @abstractmethod
    def process_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Process webhook event from the gateway
        
        Args:
            payload: Webhook payload
            headers: HTTP headers (for signature verification)
        
        Returns:
            Dict containing:
                - event_type: Type of event
                - transaction_id: Gateway's transaction identifier
                - status: Payment status
                - Any other event data
        
        Raises:
            Exception: If webhook processing fails or signature is invalid
        """
        pass
    
    @abstractmethod
    def create_refund(self, transaction_id: str, amount: float = None) -> Dict[str, Any]:
        """
        Create a refund for a payment
        
        Args:
            transaction_id: Gateway's transaction identifier
            amount: Amount to refund (None for full refund)
        
        Returns:
            Dict containing:
                - refund_id: Gateway's refund identifier
                - status: Refund status
                - amount: Refunded amount
        
        Raises:
            Exception: If refund creation fails
        """
        pass
