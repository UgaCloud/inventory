from django import forms
from django.forms import ModelForm, inlineformset_factory
import app
from app.models.transactions import (
    PurchaseOrder, Sales, StockTransfer, PurchaseOrderItem, SalesItem, StockMovement,
    TransferRequest, StockTransferItem, TransferRequestItem, StockAdjustment, StockAdjustmentItem
)
from app.models.finance import PaymentMethod
from app.models.products import Product, ProductUnitPrice, StoreLocation
from decimal import Decimal

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
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),  
            'product': forms.Select(attrs={
                'class': 'select2',})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        

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
        fields = ['receipt_no', 'customer', 'store', 'note', 'amount_paid', 'balance', 'amount_received', 'change', 'payment_method']
        labels = {
            'payment_method': '',  # Hide label for payment_method
        }
        widgets = {
            'customer': forms.Select(attrs={
                'class': 'select2',
                'style': 'width:100%'
            }),
            'receipt_no': forms.HiddenInput(attrs={
                'placeholder': 'Leave blank for auto-generation',
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make receipt_no field optional since it can be auto-generated
        self.fields['receipt_no'].required = False
        self.fields['receipt_no'].help_text = 'Leave blank to auto-generate based on store and year'
        # Make payment method field required
        self.fields['payment_method'].required = True
        
        # Filter stores to show only the default store
        try:
            default_store = StoreLocation.objects.filter(is_default=True).first()
            if default_store:
                self.fields['store'].queryset = StoreLocation.objects.filter(id=default_store.id)
                # Optionally set the default store as the initial value
                self.fields['store'].initial = default_store
            else:
                # If no default store exists, show all stores as fallback
                self.fields['store'].queryset = StoreLocation.objects.all()
        except Exception:
            # Fallback to all stores if there's an error
            self.fields['store'].queryset = StoreLocation.objects.all()
        
        # Pre-select the default payment method
        try:
            default_payment_method = PaymentMethod.objects.filter(is_default=True).first()
            if default_payment_method:
                self.fields['payment_method'].initial = default_payment_method
            else:
                # If no default payment method exists, try to set 'Cash' as default
                cash_method = PaymentMethod.objects.filter(name__icontains='cash').first()
                if cash_method:
                    self.fields['payment_method'].initial = cash_method
        except Exception:
            # If PaymentMethod model doesn't exist or there's an error, skip
            pass

    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure at least one item is present (handled in formset, but double check)
        if self.instance.pk and self.instance.items.count() == 0:
            raise forms.ValidationError("A sale must have at least one item.")
        
        # Restrict sales with balance but without a customer
        balance = cleaned_data.get('balance')
        customer = cleaned_data.get('customer')
       
        if balance and balance > 0 and not customer:
            raise forms.ValidationError("A customer must be selected for sales with due balance.")
        return cleaned_data

class SalesItemForm(ModelForm):
    class Meta:
        model = SalesItem
        fields = "__all__"
        widgets = {
            'product': forms.Select(attrs={
                'class': 'select2',
                'style': 'width:100%'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        sale_price = cleaned_data.get('sale_price')
        product = cleaned_data.get('product')
        unit = cleaned_data.get('unit')
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        if sale_price is not None and sale_price < 0:
            raise forms.ValidationError("Sale price cannot be negative.")

        # Enforce floor price based on ProductUnitPrice (if configured)
        if product and sale_price is not None:
            try:
                up = None
                if unit:
                    up = ProductUnitPrice.objects.filter(product=product, unit=unit).first()
                if not up:
                    # fallback to product's first configured unit price
                    up = product.unit_prices.order_by('id').first()
                
                if up and hasattr(up, 'price'):
                    min_price = Decimal(str(up.price))
                    # sale_price may already be Decimal, but ensure Decimal for safe compare
                    sp = Decimal(str(sale_price))
                    if sp < min_price:
                        raise forms.ValidationError(
                            f"Sale price ({sp}) cannot be below configured unit price ({min_price}) for {product.name}."
                        )
            except forms.ValidationError:
                # Re-raise validation errors
                raise
            except Exception as e:
                # Log unexpected errors but don't fail validation entirely
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error during price validation: {e}")
                pass

        return cleaned_data

class TransferRequestForm(forms.ModelForm):

    class Meta:
        model = TransferRequest
        fields = "__all__"

        exclude = ['approved_by', 'note', 'status', 'requested_by']

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

    # def clean(self):
    #     cleaned_data = super().clean()
    #     # Ensure transfer_request is set
    #     if not cleaned_data.get('transfer_request'):
    #         raise forms.ValidationError("A transfer request must be selected.")
    #     return cleaned_data

class StockTransferItemForm(forms.ModelForm):
    class Meta:
        model = StockTransferItem
        fields = "__all__"
        widgets = {
            'stock_transfer': forms.HiddenInput(),
            'transfer_request_item': forms.HiddenInput(),
            'product': forms.Select(attrs={
                'class': 'select2',
                'style': 'width:100%'
            }),
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
            'product': forms.Select(attrs={
                'class': 'select2',
                'style': 'width:100%'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return cleaned_data

class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        # exclude fields managed by system
        exclude = ['created_at', 'status', 'approved_by', 'approved_at']

    def clean(self):
        cleaned_data = super().clean()
        # basic validation can be extended
        return cleaned_data

class StockAdjustmentItemForm(ModelForm):
    class Meta:
        model = StockAdjustmentItem
        fields = ['product', 'unit', 'quantity_change', 'unit_cost', 'reason']
        
        widgets = {
            'product': forms.Select(attrs={'class': 'select2', 'style': 'width:100%'}),
            'unit': forms.Select(attrs={'class': 'select2'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        qty = cleaned_data.get('quantity_change')
        unit_cost = cleaned_data.get('unit_cost')
        if qty is None or qty == 0:
            raise forms.ValidationError('Quantity change must be non-zero.')
        if unit_cost is not None and unit_cost < 0:
            raise forms.ValidationError('Unit cost cannot be negative.')
        return cleaned_data

PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder, PurchaseOrderItem, fields='__all__', extra=1
)

StockTransferItemFormSet = inlineformset_factory(
    StockTransfer, StockTransferItem, form=StockTransferItemForm, extra=1, can_delete=True
)

TransferRequestItemFormSet = inlineformset_factory(
    TransferRequest, TransferRequestItem, fields='__all__', extra=0
)

SalesItemFormSet = inlineformset_factory(
    Sales, SalesItem, form=SalesItemForm, extra=0, can_delete=True
)

StockAdjustmentItemFormSet = inlineformset_factory(
    StockAdjustment, StockAdjustmentItem, form=StockAdjustmentItemForm, extra=1, can_delete=True
)

