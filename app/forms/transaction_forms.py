from django.forms import ModelForm
from app.models.transactions import PurchaseOrder, Sales, StockTransfer

class PurchaseOrderForm(ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ("__all__")

class SalesForm(ModelForm):
    class Meta:
        model = Sales
        fields = ("__all__")

class StockTransferForm(ModelForm):
    class Meta:
        model = StockTransfer
        fields = ("__all__")