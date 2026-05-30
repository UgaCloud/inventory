from django import forms
from app.models.products import Automotive


class AutomotiveForm(forms.ModelForm):
    class Meta:
        model = Automotive
        fields = ['brand', 'model', 'year_from', 'year_to', 'engine_type']
        widgets = {
            'brand': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Toyota',
            }),
            'model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Corolla',
            }),
            'year_from': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 2015',
            }),
            'year_to': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 2023 (leave blank for present)',
            }),
            'engine_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Diesel, Petrol, Electric',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        year_from = cleaned_data.get('year_from')
        year_to = cleaned_data.get('year_to')
        if year_from and year_to and year_from > year_to:
            raise forms.ValidationError("Year from cannot be greater than year to.")
        return cleaned_data
