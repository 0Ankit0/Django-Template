"""Khalti payment gateway adapter"""

import hashlib
import hmac
from typing import Any

import requests
from django.conf import settings


class KhaltiGateway:
    """Khalti payment gateway implementation"""

    def __init__(self):
        self.secret_key = settings.PAYMENT_GATEWAYS["khalti"]["secret_key"]
        self.live_mode = settings.PAYMENT_GATEWAYS["khalti"]["live_mode"]
        self.base_url = "https://khalti.com/api/v2/" if self.live_mode else "https://a.khalti.com/api/v2/"

    def _get_headers(self) -> dict[str, str]:
        """Get API headers with authorization"""
        return {
            "Authorization": f"Key {self.secret_key}",
            "Content-Type": "application/json",
        }

    def _npr_to_paisa(self, amount_npr: float) -> int:
        """Convert NPR to paisa (1 NPR = 100 paisa)"""
        return int(amount_npr * 100)

    def _paisa_to_npr(self, amount_paisa: int) -> float:
        """Convert paisa to NPR"""
        return amount_paisa / 100

    def _map_status(self, khalti_status: str) -> str:
        """Map Khalti status to generic status"""
        status_map = {
            "Completed": "completed",
            "Pending": "pending",
            "Refunded": "refunded",
            "User canceled": "cancelled",
            "Partially refunded": "refunded",
        }
        return status_map.get(khalti_status, "failed")

    def initiate_payment(
        self, amount: float, currency: str, customer_info: dict[str, Any], metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Initiate Khalti payment

        Args:
            amount: Amount in NPR
            currency: Should be 'NPR'
            customer_info: Dict with customer_name, customer_email, customer_phone
            metadata: Dict with purchase_order_id, purchase_order_name, return_url
        """
        if currency != "NPR":
            raise ValueError("Khalti only supports NPR currency")

        # Convert NPR to paisa
        amount_paisa = self._npr_to_paisa(amount)

        # Prepare payload
        website_url = metadata.get("website_url") or (
            settings.VITE_WEB_APP_URL if hasattr(settings, "VITE_WEB_APP_URL") else None
        )
        return_url = metadata.get("return_url")

        # Validation Logic based on Environment
        is_live = self.live_mode or not settings.DEBUG

        if not website_url:
            if is_live:
                raise ValueError("Website URL is required for Khalti live payments")
            website_url = "http://localhost:8000"  # Default for local testing

        if not return_url:
            raise ValueError("Return URL is required for Khalti payment")

        # Strict HTTPS check for Prod
        if is_live:
            if not website_url.startswith("https://"):
                # Warning or Error? Khalti might strictly require HTTPS for website_url in prod
                pass
            if not return_url.startswith("https://"):
                raise ValueError("Return URL must be HTTPS in production/live mode")

        # Basic phone number cleaning/validation (Khalti expects 10 digits)
        phone = customer_info.get("customer_phone", "")
        if phone:
            phone = "".join(filter(str.isdigit, str(phone)))
            if len(phone) > 10:
                phone = phone[-10:]
            elif len(phone) < 10:
                # In strict mode, maybe we should fail?
                # For now, let's keep the permissive behavior but maybe ensure it's not empty if required
                pass
        else:
            # Khalti requires phone. If missing, we can try to send a dummy in DEBUG,
            # but in PROD it likely needs a real phone.
            if not is_live:
                phone = "9800000000"  # Test phone for sandbox

        payload = {
            "return_url": return_url,
            "website_url": website_url,
            "amount": amount_paisa,
            "purchase_order_id": metadata.get("purchase_order_id"),
            "purchase_order_name": metadata.get("purchase_order_name"),
            "customer_info": {
                "name": customer_info.get("customer_name"),
                "email": customer_info.get("customer_email"),
                "phone": phone,
            },
        }

        # Make API request
        response = requests.post(
            f"{self.base_url}epayment/initiate/", json=payload, headers=self._get_headers(), timeout=30
        )

        if response.status_code != 200:
            raise Exception(f"Khalti API error: {response.text}")

        data = response.json()

        return {
            "payment_url": data.get("payment_url"),
            "transaction_id": data.get("pidx"),
            "expires_at": data.get("expires_at"),
            "expires_in": data.get("expires_in"),
        }

    def verify_payment(self, transaction_id: str) -> dict[str, Any]:
        """
        Verify Khalti payment status

        Args:
            transaction_id: Khalti's pidx
        """
        payload = {"pidx": transaction_id}

        response = requests.post(
            f"{self.base_url}epayment/lookup/", json=payload, headers=self._get_headers(), timeout=30
        )

        if response.status_code != 200:
            raise Exception(f"Khalti verification error: {response.text}")

        data = response.json()

        return {
            "status": self._map_status(data.get("status")),
            "amount": self._paisa_to_npr(data.get("total_amount", 0)),
            "currency": "NPR",
            "transaction_id": data.get("pidx"),
            "fee": self._paisa_to_npr(data.get("fee", 0)),
            "refunded": data.get("refunded", False),
            "payment_method": data.get("payment_method"),
            "raw_response": data,
        }

    def process_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """
        Process Khalti webhook

        Args:
            payload: Webhook payload
            headers: HTTP headers containing X-Khalti-Signature
        """
        # Verify webhook signature
        signature = headers.get("X-Khalti-Signature", "")
        if not self._verify_signature(payload, signature):
            raise Exception("Invalid webhook signature")

        # Extract event data
        event_type = payload.get("event_type", "payment.success")
        data = payload.get("data", {})
        pidx = data.get("pidx")

        # Verify the payment
        verification_result = self.verify_payment(pidx)

        return {
            "event_type": event_type,
            "transaction_id": pidx,
            "status": verification_result["status"],
            "amount": verification_result["amount"],
            "currency": "NPR",
            "raw_payload": payload,
        }

    def _verify_signature(self, payload: dict[str, Any], signature: str) -> bool:
        """Verify Khalti webhook signature using HMAC-SHA256"""
        import json

        # Create HMAC signature
        message = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        expected_signature = hmac.new(
            self.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    def create_refund(self, transaction_id: str, amount: float = None) -> dict[str, Any]:
        """
        Create refund for Khalti payment

        Note: Khalti refunds are typically processed manually through their dashboard
        This method is a placeholder for future API support
        """
        raise NotImplementedError("Khalti refunds must be processed through the Khalti dashboard")
