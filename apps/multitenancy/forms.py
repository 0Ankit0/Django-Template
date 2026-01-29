from django import forms
from apps.theme.forms import TailwindFormMixin

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
