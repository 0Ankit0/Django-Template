from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

User = get_user_model()


class TailwindFormMixin:
    """Mixin to add Tailwind/DaisyUI classes to form fields."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            css_class = 'input input-bordered w-full'
            if field.widget.__class__.__name__ == 'CheckboxInput':
                css_class = 'checkbox checkbox-primary'
            elif field.widget.__class__.__name__ == 'Select':
                css_class = 'select select-bordered w-full'
            elif field.widget.__class__.__name__ == 'Textarea':
                css_class = 'textarea textarea-bordered w-full'
            elif field.widget.__class__.__name__ == 'FileInput':
                css_class = 'file-input file-input-bordered w-full'
            
            existing_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing_class} {css_class}'.strip()
            
            if field.required:
                field.widget.attrs['required'] = True


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
        from apps.users.models import UserProfile
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
        if self.user and 'email' in self.cleaned_data:
            self.user.email = self.cleaned_data['email']
            if commit:
                self.user.save()
        if commit:
            profile.save()
        return profile


class TenantForm(TailwindFormMixin, forms.Form):
    """Form for creating/editing tenants."""
    
    name = forms.CharField(
        max_length=100,
        label='Organization Name',
        widget=forms.TextInput(attrs={'placeholder': 'Enter organization name'})
    )


class TenantInvitationForm(TailwindFormMixin, forms.Form):
    """Form for inviting members to a tenant."""
    
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'placeholder': 'Enter email to invite'})
    )
    role = forms.ChoiceField(
        choices=[
            ('member', 'Member'),
            ('admin', 'Admin'),
        ],
        label='Role',
        initial='member'
    )


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


class DocumentUploadForm(TailwindFormMixin, forms.Form):
    """Form for uploading documents."""
    
    file = forms.FileField(
        label='Select File',
        widget=forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.txt,.png,.jpg,.jpeg'})
    )
    description = forms.CharField(
        max_length=255,
        required=False,
        label='Description',
        widget=forms.Textarea(attrs={'placeholder': 'Optional description', 'rows': 3})
    )
