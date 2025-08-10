from django.forms import ModelForm
from app.models.customers import Customer, Payment

class CustomerForm(ModelForm):
    class Meta:
        model = Customer
        fields = ("__all__")

class PaymentForm(ModelForm):
    class Meta:
        model = Payment
        fields = ("customer", "amount", "payment_method", "reference", "note")