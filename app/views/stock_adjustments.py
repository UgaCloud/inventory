from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone

from app.models.products import Product, StoreLocation
from app.models.products import Inventory
from app.models.transactions import StockAdjustment
from app.forms.transaction_forms import StockAdjustmentForm, StockAdjustmentForm2

@login_required
def stock_adjustment_list(request):
    adjustments = StockAdjustment.objects.all().order_by('-created_at')

    form = StockAdjustmentForm()

    context = {
        'adjustments': adjustments,
        'form': form,
    }

    return render(request, 'stock/stock_adjustment_list.html', context)


@login_required
def adjust_stock_view(request):
    """
    Handle POST from modal to create & apply a StockAdjustment row for a store.
    Supports both Django form submission and raw POST data.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid method')

    # First, try to use the Django form for validation
    form = StockAdjustmentForm(request.POST)
    
    # Also check for raw POST fields (adjustment_type + quantity approach)
    adjustment_type = request.POST.get('adjustment_type')
    qty = request.POST.get('quantity')
    
    # If using raw POST with adjustment_type and quantity, convert to form data
    if adjustment_type and qty and not form.is_valid():
        try:
            qty_int = int(qty)
            if qty_int <= 0:
                messages.error(request, 'Quantity must be a positive integer.')
                return redirect(request.META.get('HTTP_REFERER', '/'))
            qty_change = qty_int if adjustment_type == 'increase' else -qty_int
            
            # Create form data from raw POST
            form_data = request.POST.copy()
            if 'product_id' in form_data:
                form_data['product'] = form_data['product_id']
            if 'store_id' in form_data:
                form_data['store'] = form_data['store_id']
            form_data['quantity_change'] = qty_change
            form = StockAdjustmentForm(form_data)
        except (ValueError, TypeError):
            messages.error(request, 'Quantity must be a valid positive integer.')
            return redirect(request.META.get('HTTP_REFERER', '/'))

    # Validate the form
    if not form.is_valid():
        # Check what fields were actually submitted
        submitted_fields = list(request.POST.keys())
        
        # Check for missing required fields
        missing_fields = []
        cleaned_data = getattr(form, 'cleaned_data', {})
        
        if not request.POST.get('product') and not request.POST.get('product_id'):
            missing_fields.append('product')
        if not request.POST.get('store') and not request.POST.get('store_id'):
            missing_fields.append('store')
        if not request.POST.get('quantity_change') and not (adjustment_type and qty):
            missing_fields.append('quantity_change (or adjustment_type + quantity)')
        
        # Build error message
        if missing_fields:
            error_msg = f'Missing required fields for stock adjustment: {", ".join(missing_fields)}.'
            # Add what was actually received for debugging
            if request.user.is_superuser:  # Only show detailed errors to superusers
                error_msg += f' Received fields: {", ".join([f for f in submitted_fields if f not in ["csrfmiddlewaretoken"]])}'
            messages.error(request, error_msg)
        else:
            # Show form validation errors
            error_messages = []
            for field, errors in form.errors.items():
                error_messages.append(f"{field}: {', '.join(errors)}")
            messages.error(request, f'Form validation errors: {"; ".join(error_messages)}')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    # Form is valid, proceed with creating adjustment
    try:
        with transaction.atomic():
            adj = form.save(commit=False)
            adj.created_by = request.user
            adj.status = 'pending'
            adj.save()
            
            applied = adj.apply(applied_by=str(request.user))
            if applied:
                messages.success(request, f'Applied adjustment for {adj.product.name}: {adj.quantity_change:+d}.')
            else:
                messages.warning(request, 'Adjustment saved but not applied.')
    except Exception as e:
        messages.error(request, f'Error applying adjustment: {str(e)}')

    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def api_inventory_available(request):
    """
    GET: ?product_id=&store_id=  -> returns {'success': True, 'available': <int>}
    """
    product_id = request.GET.get('product_id')
    store_id = request.GET.get('store_id')
    if not product_id or not store_id:
        return JsonResponse({'success': False, 'error': 'missing params'})

    try:
        inv = Inventory.objects.filter(product_id=product_id, store_id=store_id).first()
        available = inv.quantity_in_stock if inv else 0
        return JsonResponse({'success': True, 'available': available})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})