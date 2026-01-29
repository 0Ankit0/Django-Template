from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from apps.finances import models as finance_models
from apps.multitenancy import models as tenant_models
from apps.notifications import models as notification_models

from . import forms

User = get_user_model()


# =============================================================================
# Home & Landing Pages
# =============================================================================

class HomeView(TemplateView):
    """Landing page."""
    template_name = 'home.html'


# =============================================================================
# Authentication Views
# =============================================================================

class LoginView(FormView):
    """User login view."""
    template_name = 'auth/login.html'
    form_class = forms.LoginForm
    success_url = reverse_lazy('frontend:dashboard')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('frontend:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me')
        
        user = authenticate(self.request, username=username, password=password)
        
        if user is not None:
            # Check if user has OTP enabled
            if getattr(user, 'otp_enabled', False):
                self.request.session['otp_user_id'] = user.id
                return redirect('frontend:otp_verify')
            
            login(self.request, user)
            
            if not remember_me:
                self.request.session.set_expiry(0)
            
            messages.success(self.request, 'Welcome back!')
            return super().form_valid(form)
        else:
            messages.error(self.request, 'Invalid email or password.')
            return self.form_invalid(form)


class SignupView(FormView):
    """User registration view."""
    template_name = 'auth/signup.html'
    form_class = forms.SignupForm
    success_url = reverse_lazy('frontend:login')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('frontend:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        user = form.save(commit=False)
        user.username = form.cleaned_data['email']
        user.save()
        messages.success(self.request, 'Account created successfully! Please log in.')
        return super().form_valid(form)


class LogoutView(View):
    """User logout view."""
    
    def get(self, request):
        logout(request)
        messages.info(request, 'You have been logged out.')
        return redirect('frontend:login')
    
    def post(self, request):
        return self.get(request)


class OTPVerifyView(FormView):
    """OTP verification view."""
    template_name = 'auth/otp_verify.html'
    form_class = forms.OTPVerifyForm
    success_url = reverse_lazy('frontend:dashboard')
    
    def dispatch(self, request, *args, **kwargs):
        if 'otp_user_id' not in request.session:
            return redirect('frontend:login')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        user_id = self.request.session.get('otp_user_id')
        if not user_id:
            return redirect('frontend:login')
            
        user = get_object_or_404(User, id=user_id)
        otp_code = form.cleaned_data.get('otp_code')
        
        try:
            from apps.users.services import otp
            otp.validate_otp(user, otp_code)
            
            login(self.request, user)
            del self.request.session['otp_user_id']
            messages.success(self.request, 'Welcome back!')
            return super().form_valid(form)
            
        except Exception:
            messages.error(self.request, 'Invalid OTP code. Please try again.')
            return self.form_invalid(form)


class PasswordResetView(FormView):
    """Password reset request view."""
    template_name = 'auth/password_reset.html'
    form_class = forms.CustomPasswordResetForm
    success_url = reverse_lazy('frontend:password_reset_done')
    
    def form_valid(self, form):
        form.save(request=self.request)
        return super().form_valid(form)


class PasswordResetDoneView(TemplateView):
    """Password reset email sent confirmation."""
    template_name = 'auth/password_reset_done.html'


class OTPEnableView(LoginRequiredMixin, FormView):
    """Enable OTP/2FA."""
    template_name = 'auth/otp_setup.html'
    form_class = forms.OTPVerifyForm
    success_url = reverse_lazy('frontend:settings_security')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Generate OTP secret if not already verifying
        from apps.users.services import otp
        if not self.request.user.otp_base32:
            otp.generate_otp(self.request.user)
            
        # Add qr code url to context
        # We can use a JS library for QR code generation in frontend using otp_auth_url
        context['otp_auth_url'] = self.request.user.otp_auth_url
        context['secret_key'] = self.request.user.otp_base32
        return context
        
    def form_valid(self, form):
        otp_code = form.cleaned_data.get('otp_code')
        try:
            from apps.users.services import otp
            otp.verify_otp(self.request.user, otp_code)
            messages.success(self.request, 'Two-factor authentication enabled successfully!')
            return super().form_valid(form)
        except Exception:
            messages.error(self.request, 'Invalid code. Please try again.')
            return self.form_invalid(form)


class OTPDisableView(LoginRequiredMixin, View):
    """Disable OTP/2FA."""
    
    def post(self, request):
        from apps.users.services import otp
        otp.disable_otp(request.user)
        messages.info(request, 'Two-factor authentication disabled.')
        return redirect('frontend:settings_security')


# =============================================================================
# Dashboard Views
# =============================================================================

class DashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard view."""
    template_name = 'dashboard/index.html'
    login_url = reverse_lazy('frontend:login')
    
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


# =============================================================================
# Notification Views
# =============================================================================

class NotificationListView(LoginRequiredMixin, ListView):
    """List all notifications."""
    template_name = 'notifications/list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    login_url = reverse_lazy('frontend:login')
    
    def get_queryset(self):
        return notification_models.Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


@login_required
def mark_notification_read(request, pk):
    """Mark a notification as read (HTMX endpoint)."""
    notification = get_object_or_404(
        notification_models.Notification, pk=pk, user=request.user
    )
    notification.is_read = True
    notification.save()
    
    if request.headers.get('HX-Request'):
        return render(request, 'notifications/partials/notification_item.html', {
            'notification': notification
        })
    
    return redirect('frontend:notifications')


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read."""
    notification_models.Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True)
    
    messages.success(request, 'All notifications marked as read.')
    
    if request.headers.get('HX-Request'):
        return HttpResponse('')
    
    return redirect('frontend:notifications')


# =============================================================================
# Tenant Views
# =============================================================================

class TenantListView(LoginRequiredMixin, ListView):
    """List user's tenants."""
    template_name = 'tenants/list.html'
    context_object_name = 'memberships'
    login_url = reverse_lazy('frontend:login')
    
    def get_queryset(self):
        return tenant_models.TenantMembership.objects.filter(
            user=self.request.user
        ).select_related('tenant')


class TenantCreateView(LoginRequiredMixin, FormView):
    """Create a new tenant."""
    template_name = 'tenants/create.html'
    form_class = forms.TenantForm
    success_url = reverse_lazy('frontend:tenants')
    login_url = reverse_lazy('frontend:login')
    
    def form_valid(self, form):
        tenant = tenant_models.Tenant.objects.create(
            name=form.cleaned_data['name']
        )
        tenant_models.TenantMembership.objects.create(
            user=self.request.user,
            tenant=tenant,
            role='owner'
        )
        messages.success(self.request, f'Organization "{tenant.name}" created successfully!')
        return super().form_valid(form)


class TenantDetailView(LoginRequiredMixin, TemplateView):
    """Tenant detail view."""
    template_name = 'tenants/detail.html'
    login_url = reverse_lazy('frontend:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant_id = self.kwargs.get('pk')
        
        membership = get_object_or_404(
            tenant_models.TenantMembership,
            tenant_id=tenant_id,
            user=self.request.user
        )
        
        context['tenant'] = membership.tenant
        context['membership'] = membership
        context['members'] = tenant_models.TenantMembership.objects.filter(
            tenant=membership.tenant
        ).select_related('user')
        context['invitation_form'] = forms.TenantInvitationForm()
        
        return context


class TenantInviteView(LoginRequiredMixin, FormView):
    """Invite a member to a tenant."""
    template_name = 'tenants/invite.html'
    form_class = forms.TenantInvitationForm
    login_url = reverse_lazy('frontend:login')
    
    def get_success_url(self):
        return reverse('frontend:tenant_detail', kwargs={'pk': self.kwargs.get('pk')})
    
    def form_valid(self, form):
        tenant_id = self.kwargs.get('pk')
        membership = get_object_or_404(
            tenant_models.TenantMembership,
            tenant_id=tenant_id,
            user=self.request.user,
            role__in=['owner', 'admin']
        )
        
        email = form.cleaned_data['email']
        role = form.cleaned_data['role']
        
        # Create invitation
        tenant_models.TenantMembership.objects.create(
            tenant=membership.tenant,
            invitee_email_address=email,
            role=role,
            is_accepted=False
        )
        
        messages.success(self.request, f'Invitation sent to {email}!')
        return super().form_valid(form)


@login_required
def switch_tenant(request, pk):
    """Switch active tenant."""
    membership = get_object_or_404(
        tenant_models.TenantMembership,
        tenant_id=pk,
        user=request.user
    )
    
    request.session['active_tenant_id'] = membership.tenant.id
    messages.info(request, f'Switched to {membership.tenant.name}')
    
    return redirect('frontend:dashboard')


# =============================================================================
# Finances Views
# =============================================================================

class FinancesView(LoginRequiredMixin, TemplateView):
    """Finances overview."""
    template_name = 'finances/index.html'
    login_url = reverse_lazy('frontend:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get available plans
        context['plans'] = finance_models.Product.objects.filter(
            active=True
        ).prefetch_related('prices')
        
        return context


class PaymentMethodsView(LoginRequiredMixin, TemplateView):
    """Manage payment methods."""
    template_name = 'finances/payment_methods.html'
    login_url = reverse_lazy('frontend:login')


class SubscriptionView(LoginRequiredMixin, TemplateView):
    """Subscription management."""
    template_name = 'finances/subscription.html'
    login_url = reverse_lazy('frontend:login')


# =============================================================================
# Settings Views
# =============================================================================

class SettingsView(LoginRequiredMixin, TemplateView):
    """User settings view."""
    template_name = 'settings/index.html'
    login_url = reverse_lazy('frontend:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile_form'] = forms.ProfileForm(instance=self.request.user)
        context['password_form'] = forms.CustomPasswordChangeForm(user=self.request.user)
        return context


class ProfileUpdateView(LoginRequiredMixin, FormView):
    """Update user profile."""
    template_name = 'settings/profile.html'
    form_class = forms.ProfileForm
    success_url = reverse_lazy('frontend:settings')
    login_url = reverse_lazy('frontend:login')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)


class PasswordChangeView(LoginRequiredMixin, FormView):
    """Change password view."""
    template_name = 'settings/password.html'
    form_class = forms.CustomPasswordChangeForm
    success_url = reverse_lazy('frontend:settings')
    login_url = reverse_lazy('frontend:login')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Password changed successfully!')
        return super().form_valid(form)


class SecuritySettingsView(LoginRequiredMixin, TemplateView):
    """Security settings (2FA)."""
    template_name = 'settings/security.html'
    login_url = reverse_lazy('frontend:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['otp_enabled'] = getattr(self.request.user, 'otp_enabled', False)
        context['otp_form'] = forms.OTPVerifyForm()
        return context


# =============================================================================
# Document Views
# =============================================================================

class DocumentListView(LoginRequiredMixin, ListView):
    """List user's documents."""
    template_name = 'documents/list.html'
    context_object_name = 'documents'
    login_url = reverse_lazy('frontend:login')
    
    def get_queryset(self):
        from apps.content import models as content_models
        return content_models.Document.objects.filter(
            created_by=self.request.user
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['upload_form'] = forms.DocumentUploadForm()
        return context


class DocumentUploadView(LoginRequiredMixin, FormView):
    """Upload a document."""
    template_name = 'documents/upload.html'
    form_class = forms.DocumentUploadForm
    success_url = reverse_lazy('frontend:documents')
    login_url = reverse_lazy('frontend:login')
    
    def form_valid(self, form):
        from apps.content import models as content_models
        
        document = content_models.Document.objects.create(
            created_by=self.request.user,
            file=form.cleaned_data['file'],
        )
        
        messages.success(self.request, 'Document uploaded successfully!')
        
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'documents/partials/document_item.html', {
                'document': document
            })
        
        return super().form_valid(form)


@login_required
def document_delete(request, pk):
    """Delete a document."""
    from apps.content import models as content_models
    
    document = get_object_or_404(
        content_models.Document, pk=pk, created_by=request.user
    )
    document.delete()
    
    messages.success(request, 'Document deleted.')
    
    if request.headers.get('HX-Request'):
        return HttpResponse('')
    
    return redirect('frontend:documents')


# =============================================================================
# Integration Views (AI)
# =============================================================================

class SaaSIdeasView(LoginRequiredMixin, TemplateView):
    """AI SaaS Ideas Generator."""
    template_name = 'integrations/ai_ideas.html'
    login_url = reverse_lazy('frontend:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass empty form or previous data
        return context
    
    def post(self, request, *args, **kwargs):
        prompt = request.POST.get('keywords', '')
        context = self.get_context_data(**kwargs)
        context['keywords'] = prompt
        
        if not prompt:
            messages.error(request, "Please enter some keywords.")
            return self.render_to_response(context)
            
        try:
            from apps.integrations.openai.client import OpenAIClient
            
            # Split keywords
            keywords_list = [k.strip() for k in prompt.split(',') if k.strip()]
            
            # Call OpenAI service
            result = OpenAIClient.get_saas_ideas(keywords_list)
            
            # Pydantic model to dict
            context['ideas'] = result.ideas if hasattr(result, 'ideas') else []
            
        except Exception as e:
            messages.error(request, f"Error generating ideas: {str(e)}")
            
        return self.render_to_response(context)

# =============================================================================
# Product Views (Content)
# =============================================================================

class ProductListView(LoginRequiredMixin, ListView):
    """List products (CMS items)."""
    template_name = 'products/list.html'
    context_object_name = 'products'
    paginate_by = 12
    login_url = reverse_lazy('frontend:login')
    
    def get_queryset(self):
        from apps.content import models as content_models
        # Fetch published product items
        return content_models.ContentItem.objects.filter(
            content_type='product',
            is_published=True
        ).order_by('-created_at')
