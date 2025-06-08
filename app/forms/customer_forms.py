from django.forms import ModelForm
from app.models.customers import Customer

class CustomerForm(ModelForm):
    class Meta:
        model = Customer
        fields = ("__all__")