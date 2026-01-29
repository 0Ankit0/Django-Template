from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from notifications import models as notification_models
from multitenancy import models as tenant_models

def custom_400_view(request, exception=None):
    """Custom view to handle 400 Bad Request errors."""
    return render(request, 'errors/400.html', status=400)

def custom_403_view(request, exception=None):
    """Custom view to handle 403 Forbidden errors."""
    return render(request, 'errors/403.html', status=403)

def custom_404_view(request, exception=None):
    """Custom view to handle 404 Not Found errors."""
    return render(request, 'errors/404.html', status=404)

def custom_500_view(request):
    """Custom view to handle 500 Internal Server errors."""
    return render(request, 'errors/500.html', status=500)

def test_500_view(request):
    """Test view to trigger 500 Internal Server Error."""
    raise Exception("Test 500 error")

# Additional custom error views can be added here as needed.

class HomeView(TemplateView):
    """Landing page."""
    template_name = 'home.html'


class DashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard view."""
    template_name = 'dashboard/index.html'
    login_url = reverse_lazy('iam:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get recent notifications
        context['notifications'] = notification_models.Notification.objects.filter(
            user=user
        ).order_by('-created_at')[:5]
        
        # Get unread notification count
        context['unread_count'] = notification_models.Notification.objects.filter(
            user=user, is_read=False
        ).count()
        
        # Get user's tenants
        context['tenants'] = tenant_models.TenantMembership.objects.filter(
            user=user
        ).select_related('tenant')
        
        return context