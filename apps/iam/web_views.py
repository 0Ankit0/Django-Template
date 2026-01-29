from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from . import forms

User = get_user_model()

class LoginView(FormView):
    """User login view."""
    template_name = 'auth/login.html'
    form_class = forms.LoginForm
    success_url = reverse_lazy('core:dashboard') # Changed from frontend:dashboard
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
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
                return redirect('iam:otp_verify')
            
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
    success_url = reverse_lazy('iam:login')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
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
        return redirect('iam:login')
    
    def post(self, request):
        return self.get(request)


class OTPVerifyView(FormView):
    """OTP verification view."""
    template_name = 'auth/otp_verify.html'
    form_class = forms.OTPVerifyForm
    success_url = reverse_lazy('core:dashboard')
    
    def dispatch(self, request, *args, **kwargs):
        if 'otp_user_id' not in request.session:
            return redirect('iam:login')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        user_id = self.request.session.get('otp_user_id')
        if not user_id:
            return redirect('iam:login')
            
        user = get_object_or_404(User, id=user_id)
        otp_code = form.cleaned_data.get('otp_code')
        
        try:
            from iam.services import otp # Changed from apps.users.services

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
    success_url = reverse_lazy('iam:password_reset_done')
    
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
    success_url = reverse_lazy('iam:settings_security')
    login_url = reverse_lazy('iam:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Generate OTP secret if not already verifying
        from iam.services import otp

        if not self.request.user.otp_base32:
            otp.generate_otp(self.request.user)
            
        # Add qr code url to context
        context['otp_auth_url'] = self.request.user.otp_auth_url
        context['secret_key'] = self.request.user.otp_base32
        return context
        
    def form_valid(self, form):
        otp_code = form.cleaned_data.get('otp_code')
        try:
            from iam.services import otp

            otp.verify_otp(self.request.user, otp_code)
            messages.success(self.request, 'Two-factor authentication enabled successfully!')
            return super().form_valid(form)
        except Exception:
            messages.error(self.request, 'Invalid code. Please try again.')
            return self.form_invalid(form)


class OTPDisableView(LoginRequiredMixin, View):
    """Disable OTP/2FA."""
    login_url = reverse_lazy('iam:login')
    
    def post(self, request):
        from iam.services import otp

        otp.disable_otp(request.user)
        messages.info(request, 'Two-factor authentication disabled.')
        return redirect('iam:settings_security')


class SettingsView(LoginRequiredMixin, TemplateView):
    """User settings view."""
    template_name = 'settings/index.html'
    login_url = reverse_lazy('iam:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile_form'] = forms.ProfileForm(instance=self.request.user)
        context['password_form'] = forms.CustomPasswordChangeForm(user=self.request.user)
        return context


class ProfileUpdateView(LoginRequiredMixin, FormView):
    """Update user profile."""
    template_name = 'settings/profile.html'
    form_class = forms.ProfileForm
    success_url = reverse_lazy('iam:settings')
    login_url = reverse_lazy('iam:login')
    
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
    success_url = reverse_lazy('iam:settings')
    login_url = reverse_lazy('iam:login')
    
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
    login_url = reverse_lazy('iam:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['otp_enabled'] = getattr(self.request.user, 'otp_enabled', False)
        context['otp_form'] = forms.OTPVerifyForm()
        return context
