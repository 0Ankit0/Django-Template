from django import forms
from apps.theme.forms import TailwindFormMixin

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


class ProductCreateForm(TailwindFormMixin, forms.Form):
    """Form for creating a product (ContentItem)."""
    
    title = forms.CharField(
        max_length=255,
        label='Product Name',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Premium Subscription'})
    )
    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label='Price ($)',
        widget=forms.NumberInput(attrs={'placeholder': '0.00'})
    )
    description = forms.CharField(
        required=False,
        label='Description',
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Product details...'})
    )
    image = forms.URLField(
        required=False,
        label='Image URL',
        widget=forms.URLInput(attrs={'placeholder': 'https://example.com/image.jpg'})
    )

