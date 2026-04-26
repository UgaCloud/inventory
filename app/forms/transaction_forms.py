from django import forms
from django.forms import ModelForm, inlineformset_factory
from django.utils import timezone
import app
from app.models.transactions import *
from app.models.finance import PaymentMethod
from app.models.products import Product, ProductUnitPrice, StoreLocation
from decimal import Decimal

# Add this import at the top of transaction_forms.py
from app.models.products import UnitOfMeasure, Product, StoreLocation
from app.models.human_resource import Department

class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        exclude = ['recorded_by']
        
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make status field use the correct choices
        self.fields['status'].choices = [('PENDING', 'Pending'), ('RECEIVED', 'Received')]
        # Set initial status to PENDING for new orders
        if not self.instance.pk:
            self.fields['status'].initial = 'PENDING'

    def clean(self):
        cleaned_data = super().clean()
        expected_date = cleaned_data.get('expected_date')
        purchase_date = cleaned_data.get('purchase_date')
        if expected_date and purchase_date and expected_date < purchase_date:
            raise forms.ValidationError("Expected date cannot be before purchase date.")
        return cleaned_data

class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = "__all__"
        
        widgets = {
            'order': forms.HiddenInput(),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),  
            'product': forms.Select(attrs={'class': 'select2'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store original values for duplicate checking
        if self.instance and self.instance.pk:
            self.original_product_id = self.instance.product_id
            self.original_unit_id = self.instance.unit_id

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        unit_cost = cleaned_data.get('unit_cost')
        product = cleaned_data.get('product')
        unit = cleaned_data.get('unit')
        order = cleaned_data.get('order')
        
        # Safely create order representation without calling __str__
        order_repr = "No order"
        if order:
            if order.pk:
                order_repr = f"PO-{order.pk}"
            else:
                order_repr = "New Order"
        
        print(f"Cleaning item: product={product}, unit={unit}, order={order_repr}")
        
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        if unit_cost is not None and unit_cost < 0:
            raise forms.ValidationError("Unit cost cannot be negative.")
        
        # Skip duplicate validation for existing items
        if self.instance and self.instance.pk:
            print(f"This is an existing item (ID: {self.instance.pk}) - skipping duplicate check")
            return cleaned_data
        
        # Only check for duplicates for NEW items
        if order and order.pk and product and unit:
            print(f"Checking for duplicates: order={order.pk}, product={product}, unit={unit}")
            # Check if this combination already exists in the order
            duplicate_qs = PurchaseOrderItem.objects.filter(
                order=order,
                product=product,
                unit=unit
            )
            if duplicate_qs.exists():
                raise forms.ValidationError(
                    f"An item with product '{product}' and unit '{unit}' already exists in this order."
                )
        
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
                self.fields['store'].queryset = StoreLocation.objects.filter(is_default=True)
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
    required_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
        help_text="Optional: When this transfer is needed by"
    )
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Explain why this transfer is needed...'}),
        required=False,
        help_text="Optional: Provide a reason for this transfer"
    )

    class Meta:
        model = TransferRequest
        fields = "__all__"
        exclude = ['approved_by', 'note', 'status', 'requested_by', 'approved_date']
        widgets = {
            'required_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Explain why this transfer is needed...'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Set up department field
        self.fields['department'].queryset = Department.objects.filter(is_active=True)
        self.fields['department'].required = True
        self.fields['department'].empty_label = "Select Department"
        
        # Set up store fields
        self.fields['from_store'].queryset = StoreLocation.objects.filter(is_active=True)
        self.fields['to_store'].queryset = StoreLocation.objects.filter(is_active=True)
        
        # Set initial department from user profile if available
        if not self.instance.pk and self.request and hasattr(self.request.user, 'profile'):
            user_profile = self.request.user.profile
            if user_profile.department:
                # Try to find the department object from the name
                try:
                    department_obj = Department.objects.get(name=user_profile.department, is_active=True)
                    self.fields['department'].initial = department_obj
                except Department.DoesNotExist:
                    pass
            # Alternatively, if user has an employee record with department
            elif hasattr(user_profile, 'employee') and user_profile.employee:
                self.fields['department'].initial = user_profile.employee.department
        
        # Add CSS classes for better styling
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        from_store = cleaned_data.get('from_store')
        to_store = cleaned_data.get('to_store')
        
        # Validate store selection
        if from_store and to_store and from_store == to_store:
            raise forms.ValidationError("Source and destination stores must be different.")
        
        # Validate required date is not in the past
        required_date = cleaned_data.get('required_date')
        if required_date and required_date < timezone.now().date():
            raise forms.ValidationError("Required date cannot be in the past.")
        
        # Validate department is selected
        department = cleaned_data.get('department')
        if not department:
            raise forms.ValidationError("Please select a department for this transfer request.")
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set requested_by if it's a new instance and request is available
        if not instance.pk and self.request:
            instance.requested_by = self.request.user
        
        if commit:
            # Persist form-only fields into model fields where applicable
            # 'reason' form maps to model.note
            try:
                reason = self.cleaned_data.get('reason')
                if reason is not None:
                    instance.note = reason
            except Exception:
                pass

            try:
                required_date = self.cleaned_data.get('required_date')
                if required_date is not None:
                    instance.required_date = required_date
            except Exception:
                pass

            try:
                priority = self.cleaned_data.get('priority')
                if priority is not None:
                    instance.priority = priority
            except Exception:
                pass

            instance.save()
        
        return instance

class TransferRequestApprovalForm(forms.ModelForm):

    class Meta:
        model = TransferRequest
        fields = ['status', 'approved_by', 'note']


class StockTransferForm(forms.ModelForm):
    class Meta:
        model = StockTransfer
        fields = ['from_store', 'to_store', 'note', 'status', 'transfer_request', 'created_by']
        widgets = {
            'from_store': forms.Select(attrs={
                'class': 'form-control',
                'required': 'required'
            }),
            'to_store': forms.Select(attrs={
                'class': 'form-control', 
                'required': 'required'
            }),
            'note': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Optional notes about this transfer...'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'transfer_request': forms.HiddenInput(),
            'created_by': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Always set the store queryset
        self.fields['from_store'].queryset = StoreLocation.objects.filter(is_active=True)
        self.fields['to_store'].queryset = StoreLocation.objects.filter(is_active=True)
        
        # Make these fields not required since we'll set them in the view
        self.fields['transfer_request'].required = False
        self.fields['created_by'].required = False
        
        # Set initial status for new forms
        if not self.instance.pk:
            self.fields['status'].initial = 'pending'

    def clean(self):
        cleaned_data = super().clean()
        from_store = cleaned_data.get('from_store')
        to_store = cleaned_data.get('to_store')
        
        if from_store and to_store and from_store == to_store:
            raise forms.ValidationError("Source and destination stores cannot be the same.")
        
        return cleaned_data

class StockTransferItemForm(forms.ModelForm):
    class Meta:
        model = StockTransferItem
        fields = ['product', 'quantity', 'units']  # REMOVED 'stock_transfer' and 'transfer_request_item'
        widgets = {
            'product': forms.Select(attrs={
                'class': 'select2',
                'style': 'width:100%'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'units': forms.Select(attrs={
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit to active products
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        
        # Set required attributes
        self.fields['product'].required = True
        self.fields['quantity'].required = True
        self.fields['units'].required = True

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return quantity

StockTransferItemFormSet = forms.inlineformset_factory(
    StockTransfer,
    StockTransferItem,
    form=StockTransferItemForm,
    extra=1,  # Number of empty forms to show
    can_delete=True,
    min_num=1,
    validate_min=True,
    fields=['product', 'quantity', 'units']  # Explicitly specify fields
)


class TransferRequestItemForm(forms.ModelForm):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select product-select'})
    )
    
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Quantity'})
    )
    
    units = forms.ModelChoiceField(
        queryset=UnitOfMeasure.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )

    class Meta:
        model = TransferRequestItem
        fields = ['product', 'quantity', 'units']
        widgets = {
            'notes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional notes...'}),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return quantity

# Formset for transfer request items
TransferRequestItemFormSet = forms.inlineformset_factory(
    TransferRequest,
    TransferRequestItem,
    form=TransferRequestItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
    fields=['product', 'quantity', 'units']
)


class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = ['store', 'product', 'unit', 'quantity_change', 'unit_cost', 'reference', 'reason']
        widgets = {
            'store': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'product': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'quantity_change': forms.NumberInput(attrs={
                'class': 'form-control',
                'required': True,
                'step': '1',
                'placeholder': 'Enter positive for increase, negative for decrease'
            }),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'store': 'Store',
            'product': 'Product',
            'unit': 'Unit of Measure',
            'quantity_change': 'Quantity Change',
            'unit_cost': 'Unit Cost',
            'reference': 'Reference',
            'reason': 'Reason',
        }
        help_texts = {
            'quantity_change': 'Enter positive number to increase stock, negative to decrease (e.g., +10 or -5)',
        }

    def clean(self):
        cleaned_data = super().clean()
        quantity_change = cleaned_data.get('quantity_change')
        
        if quantity_change is not None and quantity_change == 0:
            raise forms.ValidationError({
                'quantity_change': 'Quantity change cannot be zero. Use positive number to increase or negative to decrease.'
            })
        
        return cleaned_data

class StockAdjustmentForm2(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = ['store', 'product', 'unit', 'quantity_change', 'unit_cost', 'reference', 'reason']

        widgets = {
            'product': forms.Select(attrs={'class': 'select2', 'style': 'width:100%'}),
            'unit': forms.Select(attrs={'class': 'select2'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        
        return cleaned_data

PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder, 
    PurchaseOrderItem, 
    form=PurchaseOrderItemForm,  # Use your custom form
    extra=1, 
    can_delete=True,
    fields='__all__'
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
    StockAdjustment, StockAdjustmentItem, fields='__all__', extra=1, can_delete=True
)

