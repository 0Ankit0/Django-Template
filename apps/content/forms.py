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
