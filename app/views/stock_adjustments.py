from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone

from app.models.products import Product, StoreLocation
from app.models.products import Inventory
from app.models.transactions import StockAdjustment

@login_required
def adjust_stock_view(request):
    """
    Handle POST from modal to create & apply a StockAdjustment row for a store.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid method')

    product_id = request.POST.get('product_id')
    store_id = request.POST.get('store_id')
    adjustment_type = request.POST.get('adjustment_type')
    qty = request.POST.get('quantity')
    reason = request.POST.get('reason', '').strip()

    if not all([product_id, store_id, adjustment_type, qty]):
        messages.error(request, 'Missing required fields for stock adjustment.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    try:
        qty = int(qty)
        if qty <= 0:
            raise ValueError
    except ValueError:
        messages.error(request, 'Quantity must be a positive integer.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    product = get_object_or_404(Product, pk=product_id)
    store = get_object_or_404(StoreLocation, pk=store_id)
    qty_change = qty if adjustment_type == 'increase' else -qty

    try:
        with transaction.atomic():
            adj = StockAdjustment.objects.create(
                store=store,
                reference=None,
                created_by=str(request.user),
                status='pending',
                product=product,
                unit=None,
                quantity_change=qty_change,
                reason=reason,
                unit_cost=None,
                item_created_at=timezone.now(),
            )
            applied = adj.apply(applied_by=str(request.user))
            if applied:
                messages.success(request, f'Applied adjustment for {product.name}: {qty_change}.')
            else:
                messages.warning(request, 'Adjustment saved but not applied.')
    except Exception as e:
        messages.error(request, f'Error applying adjustment: {e}')

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