from django import forms

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
