from django.contrib import admin
from djstripe import admin as djstripe_admin
from djstripe import models as djstripe_models
from .models import PaymentTransaction, WebhookEvent

admin.site.unregister(djstripe_models.PaymentIntent)
admin.site.unregister(djstripe_models.Charge)


@admin.register(djstripe_models.PaymentIntent)
class PaymentIntentAdmin(djstripe_admin.StripeModelAdmin):
    change_form_template = "djstripe/paymentintent/admin/change_form.html"


@admin.register(djstripe_models.Charge)
class ChargeAdmin(djstripe_admin.StripeModelAdmin):
    change_form_template = "djstripe/charge/admin/change_form.html"


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    """Admin interface for PaymentTransaction"""
    
    list_display = [
        'id',
        'gateway',
        'amount',
        'currency',
        'status',
        'payment_method',
        'tenant',
        'created_at',
    ]
    list_filter = [
        'gateway',
        'status',
        'currency',
        'created_at',
    ]
    search_fields = [
        'gateway_transaction_id',
        'customer_info',
    ]
    readonly_fields = [
        'id',
        'gateway_transaction_id',
        'gateway_response',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Transaction Details', {
            'fields': ('id', 'gateway', 'gateway_transaction_id', 'status')
        }),
        ('Payment Information', {
            'fields': ('amount', 'currency', 'payment_method')
        }),
        ('Customer Information', {
            'fields': ('customer_info', 'tenant')
        }),
        ('Gateway Response', {
            'fields': ('gateway_response',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def has_add_permission(self, request):
        """Disable manual creation of payment transactions"""
        return False


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    """Admin interface for WebhookEvent"""
    
    list_display = [
        'id',
        'gateway',
        'event_type',
        'processed',
        'created_at',
    ]
    list_filter = [
        'gateway',
        'processed',
        'created_at',
    ]
    search_fields = [
        'event_type',
        'payload',
    ]
    readonly_fields = [
        'id',
        'gateway',
        'event_type',
        'payload',
        'created_at',
    ]
    fieldsets = (
        ('Event Details', {
            'fields': ('id', 'gateway', 'event_type', 'processed')
        }),
        ('Payload', {
            'fields': ('payload',),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def has_add_permission(self, request):
        """Disable manual creation of webhook events"""
        return False
