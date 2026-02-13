from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from djstripe import models as djstripe_models
from multitenancy.models import Tenant
from multitenancy.models.tenant_membership import TenantMembership
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class TestSavedPayments(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Test Tenant", email="test@tenant.com", subdomain="test")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
        )
        TenantMembership.objects.create(tenant=self.tenant, user=self.user, is_accepted=True, role="OWNER")
        self.client.force_authenticate(self.user)

        # Create a dummy customer
        self.customer = djstripe_models.Customer.objects.create(
            subscriber=self.tenant,
            id="cus_test123",
            livemode=False,
            # balance=0,  <-- removed
            json_response={},
        )

    @patch("djstripe.models.SetupIntent._api_create")
    @patch("djstripe.models.SetupIntent.sync_from_stripe_data")
    def test_create_setup_intent(self, mock_sync, mock_api_create):
        """Test creating a SetupIntent for adding a card"""
        url = reverse("setup-intent-list", host="api")

        # Mock Stripe API response
        mock_api_create.return_value = {
            "id": "seti_123",
            "client_secret": "seti_123_secret",
            "customer": "cus_test123",
            "status": "requires_payment_method",
        }

        # Mock sync to return a dummy object or just pass through
        mock_sync.return_value = djstripe_models.SetupIntent(
            id="seti_123", client_secret="seti_123_secret", customer=self.customer
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["client_secret"], "seti_123_secret")

        # Verify API called with correct parameters
        mock_api_create.assert_called_with(
            customer=self.customer.id, payment_method_types=["card"], usage="off_session"
        )

    def test_list_payment_methods(self):
        """Test listing saved payment methods"""
        url = reverse("payment-method-list", host="api")

        # Create a dummy payment method
        djstripe_models.PaymentMethod.objects.create(
            id="pm_123",
            type="card",
            card={"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2030},
            billing_details={},
            customer=self.customer,
            livemode=False,
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], "pm_123")

    @patch("stripe.PaymentIntent.create")
    def test_pay_with_saved_card(self, mock_stripe_create):
        """Test initiating payment with a saved payment method"""
        url = reverse("payment-initiate", host="api")

        mock_stripe_create.return_value = MagicMock(
            id="pi_123", status="succeeded", client_secret="pi_123_secret", amount=100000, currency="npr"
        )

        data = {
            "gateway": "stripe",
            "amount": "1000.00",
            "currency": "NPR",
            "purchase_order_id": "order_123",
            "purchase_order_name": "Test Order",
            "customer_name": "Test User",
            "customer_email": "test@example.com",
            "customer_phone": "9800000000",
            "return_url": "https://example.com/return",
            "payment_method_id": "pm_123",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "completed")  # mapped from succeeded

        # Verify Stripe called correctly
        mock_stripe_create.assert_called_with(
            amount=100000,
            currency="NPR",
            customer=self.customer.id,
            payment_method="pm_123",
            off_session=True,
            confirm=True,
            metadata={
                "purchase_order_id": "order_123",
                "purchase_order_name": "Test Order",
                "return_url": "https://example.com/return",
                "website_url": None,
                "customer_id": self.customer.id,
                "payment_method_id": "pm_123",
            },
            return_url="https://example.com/return",
        )

    @patch("stripe.checkout.Session.create")
    def test_pay_with_new_card_stripe(self, mock_session_create):
        """Test initiating payment with new card (Checkout Session)"""
        url = reverse("payment-initiate", host="api")

        mock_session_create.return_value = MagicMock(
            id="cs_123", url="https://checkout.stripe.com/pay/cs_123", status="open"
        )

        data = {
            "gateway": "stripe",
            "amount": "1000.00",
            "currency": "NPR",
            "purchase_order_id": "order_123",
            "purchase_order_name": "Test Order",
            "customer_name": "Test User",
            "customer_email": "test@example.com",
            "customer_phone": "9800000000",
            "return_url": "https://example.com/return",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["client_secret"], None)

        # Verify Checkout Session created
        args, kwargs = mock_session_create.call_args
        self.assertEqual(kwargs["mode"], "payment")
        self.assertEqual(kwargs["customer"], self.customer.id)  # Should attach customer
        self.assertEqual(kwargs["payment_intent_data"]["setup_future_usage"], "off_session")  # Should set up for future
