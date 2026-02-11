from djstripe import models as djstripe_models
from django.db import models
from django.conf import settings
import uuid

from . import managers


class Product(djstripe_models.Product):
    class Meta:
        proxy = True

    objects = managers.ProductManager()


class Price(djstripe_models.Price):
    class Meta:
        proxy = True

    objects = managers.PriceManager()


class PaymentTransaction(models.Model):
    """Universal payment transaction model for all gateways"""
    
    GATEWAY_CHOICES = [
        ('stripe', 'Stripe'),
        ('khalti', 'Khalti'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, db_index=True)
    gateway_transaction_id = models.CharField(max_length=255, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    payment_method = models.CharField(max_length=50, blank=True)
    customer_info = models.JSONField(default=dict, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    tenant = models.ForeignKey('multitenancy.Tenant', on_delete=models.CASCADE, related_name='payment_transactions')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['gateway', 'status']),
        ]
    
    def __str__(self):
        return f"{self.gateway} - {self.amount} {self.currency} - {self.status}"


class WebhookEvent(models.Model):
    """Universal webhook event logging for all gateways"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway = models.CharField(max_length=20, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField()
    processed = models.BooleanField(default=False, db_index=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['gateway', 'processed']),
        ]
    
    def __str__(self):
        return f"{self.gateway} - {self.event_type} - {'Processed' if self.processed else 'Pending'}"
