from django import forms
from django.forms import ModelForm, inlineformset_factory
from app.models.transactions import (
    PurchaseOrder, Sales, StockTransfer, PurchaseOrderItem, SalesItem, StockMovement,
    TransferRequest, StockTransferItem, TransferRequestItem
)

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

    def clean(self):
        cleaned_data = super().clean()
        expected_date = cleaned_data.get('expected_date')
        purchase_date = cleaned_data.get('purchase_date')
        if expected_date and purchase_date and expected_date < purchase_date:
            raise forms.ValidationError("Expected date cannot be before purchase date.")
        return cleaned_data

class PurchaseOrderItemForm(ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = "__all__"
        widgets = {
            'order': forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        unit_cost = cleaned_data.get('unit_cost')
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        if unit_cost is not None and unit_cost < 0:
            raise forms.ValidationError("Unit cost cannot be negative.")
        return cleaned_data

class SalesForm(forms.ModelForm):
    class Meta:
        model = Sales
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        # Ensure at least one item is present (handled in formset, but double check)
        if self.instance.pk and self.instance.items.count() == 0:
            raise forms.ValidationError("A sale must have at least one item.")
        return cleaned_data

class SalesItemForm(ModelForm):
    class Meta:
        model = SalesItem
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        sale_price = cleaned_data.get('sale_price')
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        if sale_price is not None and sale_price < 0:
            raise forms.ValidationError("Sale price cannot be negative.")
        return cleaned_data

class TransferRequestForm(forms.ModelForm):

    class Meta:
        model = TransferRequest
        fields = "__all__"

        exclude = ['approved_by', 'note', 'status']

    def clean(self):
        cleaned_data = super().clean()
        from_store = cleaned_data.get('from_store')
        to_store = cleaned_data.get('to_store')
        if from_store and to_store and from_store == to_store:
            raise forms.ValidationError("Source and destination stores must be different.")
        return cleaned_data

class TransferRequestApprovalForm(forms.ModelForm):

    class Meta:
        model = TransferRequest
        fields = ['status', 'approved_by', 'note']

class StockTransferForm(forms.ModelForm):
    class Meta:
        model = StockTransfer
        fields = "__all__"
        widgets = {
            'transfer_request': forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        # Ensure transfer_request is set
        if not cleaned_data.get('transfer_request'):
            raise forms.ValidationError("A transfer request must be selected.")
        return cleaned_data

class StockTransferItemForm(forms.ModelForm):
    class Meta:
        model = StockTransferItem
        fields = "__all__"
        widgets = {
            'stock_transfer': forms.HiddenInput(),
            'transfer_request_item': forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        transfer_request_item = cleaned_data.get('transfer_request_item')
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        # Prevent transferring more than requested
        if transfer_request_item and quantity > transfer_request_item.quantity:
            raise forms.ValidationError(f"Cannot transfer more than requested ({transfer_request_item.quantity}).")
        return cleaned_data

class TransferRequestItemForm(forms.ModelForm):
    class Meta:
        model = TransferRequestItem
        fields = "__all__"
        widgets = {
            'transfer_request': forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return cleaned_data

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
