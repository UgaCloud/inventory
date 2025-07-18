from django import forms
from django.forms import ModelForm, inlineformset_factory
from app.models.transactions import *

class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        exclude = ['recorded_by']
        
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'recorded_by': 'Recorded By (User)',
        }
        help_texts = {
            'branch': 'Select the branch for this order.',
        }

class PurchaseOrderItemForm(ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = "__all__"

class SalesForm(forms.ModelForm):
    class Meta:
        model = Sales
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('total_items', 0) <= 0:
            raise forms.ValidationError("A sale must have at least one item.")
        return cleaned_data

class SalesItemForm(ModelForm):
    class Meta:
        model = SalesItem
        fields = "__all__"
        # widgets = {
        #     'product': forms.TextInput(attrs={
        #         'class': 'form-control product-autocomplete',
        #         'autocomplete': 'on',
        #         'placeholder': 'Product Name...'
        #         # The JS below will hook to this class
        #     }),
        # }

class StockTransferForm(ModelForm):
    class Meta:
        model = StockTransfer
        fields = "__all__"

class StockMovementForm(ModelForm):
    class Meta:
        model = StockMovement
        fields = "__all__"

PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder, PurchaseOrderItem, fields='__all__', extra=1
)

StockTransferItemFormSet = inlineformset_factory(
    StockTransfer, StockTransferItem, fields='__all__', extra=1
)

TransferRequestItemFormSet = inlineformset_factory(
    TransferRequest, TransferRequestItem, fields='__all__', extra=0
)

SalesItemFormSet = inlineformset_factory(
    Sales, SalesItem, form=SalesItemForm, extra=0, can_delete=True
)

