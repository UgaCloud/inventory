from django.forms import ModelForm
from django import forms
from app.models.customers import Customer, Payment

class CustomerForm(ModelForm):
    class Meta:
        model = Customer
        fields = "__all__"


# Lightweight form for quick AJAX creation (only name)
class QuickCustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ('name',)
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer name', 'required': True}),
        }

class PaymentForm(ModelForm):
    class Meta:
        model = Payment
        fields = ['customer', 'amount', 'payment_method', 'reference', 'note']

        widgets = {
            'customer': forms.HiddenInput(),}