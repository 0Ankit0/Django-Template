from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from theme.forms import TailwindFormMixin

User = get_user_model()

class LoginForm(TailwindFormMixin, AuthenticationForm):
    """Custom login form with Tailwind styling."""
    
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email', 'autofocus': True})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter your password'})
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        label='Remember me'
    )


class SignupForm(TailwindFormMixin, UserCreationForm):
    """Custom signup form with Tailwind styling."""
    
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email'})
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        label='First Name',
        widget=forms.TextInput(attrs={'placeholder': 'First name'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        label='Last Name',
        widget=forms.TextInput(attrs={'placeholder': 'Last name'})
    )
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')


class CustomPasswordResetForm(TailwindFormMixin, PasswordResetForm):
    """Custom password reset form."""
    pass


class CustomSetPasswordForm(TailwindFormMixin, SetPasswordForm):
    """Custom set password form."""
    pass


class CustomPasswordChangeForm(TailwindFormMixin, PasswordChangeForm):
    """Custom password change form."""
    pass


class ProfileForm(TailwindFormMixin, forms.ModelForm):
    """User profile update form."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Email address'})
    )
    
    avatar = forms.FileField(
        required=False,
        widget=forms.FileInput(),
        label='Profile Picture'
    )
    
    class Meta:
        from iam.models import User, UserProfile

        model = UserProfile
        fields = ('first_name', 'last_name', 'avatar')
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last name'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['email'].initial = self.user.email
            if hasattr(self.user, 'profile'):
                self.instance = self.user.profile
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Update email on user model
        if self.user and 'email' in self.cleaned_data:
            self.user.email = self.cleaned_data['email']
            if commit:
                self.user.save()
                
        # Handle Avatar
        avatar_file = self.cleaned_data.get('avatar')
        if avatar_file:
            from iam.models import UserAvatar
            
            # If profile already has an avatar, update it? Or create new one?
            # Start simple: Create new avatar instance (old one eventually GC'd or we delete it)
            # Better: if exists, update it.
            if profile.avatar:
                profile.avatar.original = avatar_file
                if commit:
                    profile.avatar.save()
            else:
                user_avatar = UserAvatar(original=avatar_file)
                if commit:
                    user_avatar.save()
                profile.avatar = user_avatar

        if commit:
            profile.save()
        return profile


class OTPVerifyForm(TailwindFormMixin, forms.Form):
    """Form for OTP verification."""
    
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        label='OTP Code',
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter 6-digit code',
            'pattern': '[0-9]{6}',
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code'
        })
    )
