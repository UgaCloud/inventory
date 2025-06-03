from django.forms import ModelForm
from app.models.suppliers import Supplier

class SupplierForm(ModelForm):
    class Meta:
        model = Supplier
        fields = ("__all__")