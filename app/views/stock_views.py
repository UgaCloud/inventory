from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from app.models.transactions import StockMovement, StockTransfer, PurchaseOrder, PurchaseOrderItem, StockAdjustment
from app.forms.transaction_forms import StockTransferForm, PurchaseOrderForm, PurchaseOrderItemForm, StockAdjustmentForm
from app.selectors.transaction_selectors import (
    get_all_stock_movements, get_stock_movements_by_branch,
    get_all_stock_transfers, get_stock_transfer_by_id, get_stock_transfers_by_branch,
    get_all_orders, get_order_by_id, get_orders_by_branch,
    get_items_by_order
)
from app.models.products import Product, UnitOfMeasure
# from app.forms.transaction_forms import StockAdjustmentItemFormSet

# Added imports for bulk upload
import csv
import io
from decimal import Decimal
from datetime import datetime

@login_required
def stock_dashboard(request):
    stock_movements = get_all_stock_movements()
    stock_transfers = get_all_stock_transfers()
    context = {
        'stock_movements': stock_movements,
        'stock_transfers': stock_transfers,
    }
    return render(request, 'stock_dashboard.html', context)

@login_required
def stock_transfer_list(request):
    transfers = get_all_stock_transfers()
    return render(request, 'stock_transfer_list.html', {'transfers': transfers})

@login_required
def stock_transfer_detail(request, transfer_id):
    transfer = get_stock_transfer_by_id(transfer_id)
    return render(request, 'stock_transfer_detail.html', {'transfer': transfer})

@login_required
def create_stock_transfer(request):
    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Stock transfer recorded successfully.')
            return redirect('stock_transfer_list')
    else:
        form = StockTransferForm()
    return render(request, 'stock_transfer_form.html', {'form': form})

@login_required
def edit_stock_transfer(request, transfer_id):
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    if request.method == 'POST':
        form = StockTransferForm(request.POST, instance=transfer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Stock transfer updated successfully.')
            return redirect('stock_transfer_list')
    else:
        form = StockTransferForm(instance=transfer)
    return render(request, 'stock_transfer_form.html', {'form': form, 'transfer': transfer})

@login_required
def delete_stock_transfer(request, transfer_id):
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    if request.method == 'POST':
        transfer.delete()
        messages.success(request, 'Stock transfer deleted successfully.')
        return redirect('stock_transfer_list')
    return render(request, 'stock_transfer_confirm_delete.html', {'transfer': transfer})

@login_required
def purchase_order_list(request):
    orders = get_all_orders()

    form = PurchaseOrderForm()

    context = {
        'purchase_orders': orders,
        'form': form,
    }
    return render(request, 'stock/purchase_order_list.html', context)

@login_required
def purchase_order_detail(request, order_id):
    order = get_order_by_id(order_id)
    return render(request, 'purchase_order_detail.html', {'order': order})

@login_required
def create_purchase_order(request):
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            order = form.save()
            messages.success(request, 'Purchase order created successfully.')
            
            return redirect(purchase_order_item_list, order_id = order.id)
    

@login_required
def edit_purchase_order(request, order_id):
    order = get_object_or_404(PurchaseOrder, id=order_id)
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Purchase order updated successfully.')
            return redirect('purchase_order_list')
    else:
        form = PurchaseOrderForm(instance=order)
    return render(request, 'purchase_order_form.html', {'form': form, 'order': order})

@login_required
def delete_purchase_order(request, order_id):
    order = get_object_or_404(PurchaseOrder, id=order_id)
    if request.method == 'POST':
        order.delete()
        messages.success(request, 'Purchase order deleted successfully.')
        return redirect('purchase_order_list')
    return render(request, 'purchase_order_confirm_delete.html', {'order': order})

@login_required
def purchase_order_item_list(request, order_id):
    order = get_object_or_404(PurchaseOrder, id=order_id)
    items = get_items_by_order(order)
    
    form = PurchaseOrderItemForm(initial={'order': order})
    
    context = {
        'order': order, 
        'items': items,
        'form': form,
    }

    return render(request, 'stock/purchase_order_item_list.html', context)

@login_required
def create_purchase_order_item(request, order_id):
    order = get_object_or_404(PurchaseOrder, id=order_id)
    
    if request.method == 'POST':
        form = PurchaseOrderItemForm(request.POST)
        
        if form.is_valid():
            item = form.save(commit=False)
            item.order = order
            item.save()
            
            messages.success(request, 'Purchase order item added successfully.')
            
        return redirect(purchase_order_item_list, order_id=order.id)
        

@login_required
def edit_purchase_order_item(request, item_id):
    item = get_object_or_404(PurchaseOrderItem, id=item_id)
    order = item.order
    if request.method == 'POST':
        form = PurchaseOrderItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Purchase order item updated successfully.')
            return redirect('purchase_order_item_list', order_id=order.id)
    else:
        form = PurchaseOrderItemForm(instance=item)
    return render(request, 'purchase_order_item_form.html', {'form': form, 'order': order, 'item': item})

@login_required
def delete_purchase_order_item(request, item_id):
    item = get_object_or_404(PurchaseOrderItem, id=item_id)
    order = item.order
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Purchase order item deleted successfully.')
        return redirect('purchase_order_item_list', order_id=order.id)
    return render(request, 'purchase_order_item_confirm_delete.html', {'item': item, 'order': order})

@login_required
def purchase_order_items_bulk_upload(request, order_id):
    """Handle CSV bulk upload to create PurchaseOrderItem records for a given PurchaseOrder.

    Expected CSV headers (case-insensitive, any of these are accepted):
      - sku, product_sku, barcode, product  (used to find Product by sku, barcode or name)
      - unit or unit_name                      (UnitOfMeasure name)
      - quantity
      - unit_cost
      - expiry_date (YYYY-MM-DD or DD/MM/YYYY)

    Rows missing product/unit/quantity or with invalid quantity are skipped. A summary message
    is shown and the user is redirected back to the purchase order item list.
    """
    order = get_object_or_404(PurchaseOrder, id=order_id)

    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            messages.error(request, 'No file uploaded.')
            return redirect(purchase_order_item_list, order_id=order.id)

        try:
            decoded = uploaded_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded)
        except Exception as e:
            messages.error(request, f'Failed to read uploaded file: {e}')
            return redirect(purchase_order_item_list, order_id=order.id)

        created = 0
        skipped = []

        for row_number, row in enumerate(reader, start=1):
            # Normalize keys
            def get_row_value(keys):
                for k in keys:
                    val = row.get(k)
                    if val:
                        return val.strip()
                return None

            product_key = get_row_value(['sku', 'product_sku', 'barcode', 'product'])
            unit_key = get_row_value(['unit', 'unit_name'])
            qty_raw = get_row_value(['quantity', 'qty'])
            cost_raw = get_row_value(['unit_cost', 'unitcost', 'cost'])
            expiry_raw = get_row_value(['expiry_date', 'expiry'])

            # Resolve product
            product = None
            if product_key:
                product = Product.objects.filter(sku__iexact=product_key).first()
                if not product:
                    product = Product.objects.filter(barcode__iexact=product_key).first()
                if not product:
                    product = Product.objects.filter(name__iexact=product_key).first()

            # Resolve unit
            unit = None
            if unit_key:
                unit = UnitOfMeasure.objects.filter(name__iexact=unit_key).first()

            # Parse numeric values
            try:
                quantity = int(float(qty_raw)) if qty_raw is not None else None
            except Exception:
                quantity = None

            try:
                unit_cost = Decimal(cost_raw) if cost_raw is not None and cost_raw != '' else Decimal(0)
            except Exception:
                unit_cost = Decimal(0)

            expiry_date = None
            if expiry_raw:
                for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    try:
                        expiry_date = datetime.strptime(expiry_raw, fmt).date()
                        break
                    except Exception:
                        continue

            # Basic validation
            if not product or not unit or not quantity or quantity <= 0:
                skipped.append((row_number, row))
                continue

            # Create PurchaseOrderItem
            try:
                poi = PurchaseOrderItem(
                    order=order,
                    product=product,
                    unit=unit,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    expiry_date=expiry_date
                )
                poi.save()
                created += 1
            except Exception as e:
                skipped.append((row_number, str(e)))
                continue

        # Update order totals if any items were created
        if created:
            try:
                order.update_total_cost()
            except Exception:
                pass

        messages.success(request, f'Bulk upload finished — created: {created}, skipped: {len(skipped)}.')
        if skipped:
            messages.warning(request, f'First skipped row: {skipped[0]} (see server logs for details).')

        return redirect(purchase_order_item_list, order_id=order.id)

@login_required
def download_purchase_order_item_template(request):
    """Return a small CSV template file for PurchaseOrderItem bulk upload."""
    # Use the same headers the bulk upload expects
    headers = ['sku', 'unit', 'quantity', 'unit_cost', 'expiry_date']

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(headers)
    # Example row — optional, helps users understand format
    writer.writerow(['PRD-0001', 'Kilogram', '10', '3500', '2026-12-31'])

    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="purchase_order_items_template.csv"'
    return response

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
def stock_adjustment_detail(request, adjustment_id):
    # Fetch fresh data from database (real-time)
    adjustment = get_object_or_404(
        StockAdjustment.objects.select_related('product', 'store', 'unit', 'created_by'),
        id=adjustment_id
    )
    adjustment.refresh_from_db()  # Ensure we have the latest data
    
    # Get all adjustments with the same reference (batch adjustments)
    related_adjustments = []
    batch_totals = {}
    if adjustment.reference:
        related_adjustments = StockAdjustment.objects.filter(
            reference=adjustment.reference,
            store=adjustment.store
        ).select_related('product', 'unit').order_by('created_at')
        
        # Calculate batch totals dynamically from fresh DB data
        from django.db.models import Sum, Count
        batch_totals = {
            'total_items': related_adjustments.count(),
            'total_quantity_change': related_adjustments.aggregate(
                total=Sum('quantity_change')
            )['total'] or 0,
            'total_value': sum(
                (abs(adj.quantity_change) * (adj.unit_cost or 0)) 
                for adj in related_adjustments 
                if adj.unit_cost
            ),
            'applied_count': related_adjustments.filter(status='applied').count(),
            'pending_count': related_adjustments.filter(status='pending').count(),
        }
    
    # Get stock movements related to this adjustment (real-time)
    stock_movements = StockMovement.objects.filter(
        transaction_type='ADJUSTMENT',
        transaction_id=adjustment.id
    ).select_related('product', 'store').order_by('-timestamp')
    
    # Get current inventory for this product/store (real-time - fresh from DB)
    from app.models.products import Inventory
    try:
        current_inventory = Inventory.objects.get(
            product=adjustment.product,
            store=adjustment.store
        )
        current_inventory.refresh_from_db()  # Get latest inventory data
        current_quantity = current_inventory.quantity_in_stock
    except Inventory.DoesNotExist:
        current_quantity = 0
    
    # Calculate quantities correctly - use adjustment data as source of truth
    if adjustment.status == 'applied' and stock_movements.exists():
        # If applied, use stock movement to get the actual stock level after adjustment
        movement = stock_movements.first()
        # units_in_stock in movement = stock AFTER the adjustment was applied (this is accurate)
        quantity_after_from_movement = movement.units_in_stock
        
        # However, use the ADJUSTMENT's quantity_change as source of truth (not movement.quantity which might be wrong)
        # Calculate before based on adjustment's quantity_change
        # before = after - adjustment_change
        quantity_before = quantity_after_from_movement - adjustment.quantity_change
        
        # Ensure quantity_before is not negative (safety check)
        if quantity_before < 0:
            quantity_before = 0
        
        # Calculate what "After Adjustment" SHOULD be based on adjustment (source of truth)
        # After = Before + Adjustment Change
        quantity_after_should_be = quantity_before + adjustment.quantity_change
        
        # Use the calculated value (what this adjustment actually did)
        # If movement.units_in_stock differs, it means other transactions happened
        quantity_after = quantity_after_should_be
        
        # Note: movement.units_in_stock may differ if other transactions occurred after this adjustment
        # We show what THIS adjustment did, not necessarily what current stock is
    elif adjustment.status == 'pending':
        # For pending adjustments, show projected values based on current stock
        quantity_before = current_quantity
        # Projected after = current + change (ensure not negative)
        quantity_after = max(0, current_quantity + adjustment.quantity_change)
    else:
        # For other statuses (approved, cancelled), show current stock only
        quantity_before = None
        quantity_after = current_quantity
    
    # Calculate total value for this adjustment (use absolute quantity for value)
    total_value = None
    if adjustment.unit_cost and adjustment.quantity_change:
        # Use absolute value of quantity change for value calculation
        # This gives the monetary value of the stock being adjusted
        total_value = abs(adjustment.quantity_change) * adjustment.unit_cost
    
    context = {
        'adjustment': adjustment,
        'related_adjustments': related_adjustments,
        'batch_totals': batch_totals,
        'stock_movements': stock_movements,
        'current_quantity': current_quantity,
        'quantity_before': quantity_before,
        'quantity_after': quantity_after,
        'total_value': total_value,
    }
    return render(request, 'stock/stock_adjustment_detail.html', context)

@login_required
def create_stock_adjustment(request):
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        # formset = StockAdjustmentItemFormSet(request.POST)
        if form.is_valid():
            adj = form.save(commit=False)
            # prefer to record username; fallback to form value
            try:
                adj.created_by = request.user.username
            except Exception:
                pass
            adj.save()

            messages.success(request, 'Stock adjustment created successfully.')
            return redirect('stock_adjustment_list')

@login_required
def edit_stock_adjustment(request, adjustment_id):
    adjustment = get_object_or_404(StockAdjustment, id=adjustment_id)
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST, instance=adjustment)

        if form.is_valid():
            form.save()
            messages.success(request, 'Stock adjustment updated successfully.')
            return redirect('stock_adjustment_detail', adjustment_id=adjustment.id)
    else:
        form = StockAdjustmentForm(instance=adjustment)
    return render(request, 'stock/stock_adjustment_form.html', {'form': form, 'adjustment': adjustment})

@login_required
def apply_stock_adjustment(request, adjustment_id):
    adjustment = get_object_or_404(StockAdjustment, id=adjustment_id)
    if request.method == 'POST':
        applied = adjustment.apply(applied_by=getattr(request.user, 'username', None))
        if applied:
            messages.success(request, 'Stock adjustment applied successfully.')
        else:
            messages.info(request, 'Stock adjustment was already applied.')
        return redirect('stock_adjustment_detail', adjustment_id=adjustment.id)
    return render(request, 'stock/stock_adjustment_confirm_apply.html', {'adjustment': adjustment})

@login_required
def delete_stock_adjustment(request, adjustment_id):
    adjustment = get_object_or_404(StockAdjustment, id=adjustment_id)
    if request.method == 'POST':
        adjustment.delete()
        messages.success(request, 'Stock adjustment deleted successfully.')
        return redirect('stock_adjustment_list')
    return render(request, 'stock/stock_adjustment_confirm_delete.html', {'adjustment': adjustment})
