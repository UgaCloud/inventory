from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from app.models.transactions import *
from app.forms.transaction_forms import *
from app.models.products import *
from app.selectors.transaction_selectors import *
from app.models.products import Product, UnitOfMeasure
# from app.forms.transaction_forms import StockAdjustmentItemFormSet

# Added imports for bulk upload
import csv
import io, json
from decimal import Decimal
from datetime import *

from django.http import JsonResponse

from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
from django.db import transaction

from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta

from app.forms.transaction_forms import StockTransferForm, StockTransferItemFormSet

from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


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
    """Proxy to canonical `stock_transfer_list` view in `app.views.transfers`.

    We keep this thin wrapper for backwards compatibility so URLs that import
    this view continue to work while the canonical implementation lives in
    `app.views.transfers.stock_transfer_list`.
    """
    # Import locally to avoid circular imports at module load time
    from app.views.transfers import stock_transfer_list as canonical_stock_transfer_list
    return canonical_stock_transfer_list(request)

@login_required
def stock_transfer_create(request):
    """Create a new stock transfer"""
    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.created_by = request.user
            transfer.save()
            messages.success(request, 'Stock transfer created successfully.')
            return redirect('stock_transfer_list')
    else:
        form = StockTransferForm()
    
    return render(request, 'stock/stock_transfer_form.html', {'form': form})

@login_required
def stock_transfer_update(request, transfer_id):
    """Update a stock transfer"""
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    
    if request.method == 'POST':
        form = StockTransferForm(request.POST, instance=transfer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Stock transfer updated successfully.')
            return redirect('stock_transfer_detail', transfer_id=transfer.id)
    else:
        form = StockTransferForm(instance=transfer)
    
    return render(request, 'stock/stock_transfer_form.html', {'form': form, 'transfer': transfer})

@login_required
def update_transfer_status(request, transfer_id):
    """Update transfer status"""
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(StockTransfer.TRANSFER_STATUS_CHOICES):
            transfer.status = new_status
            transfer.save()
            messages.success(request, f'Transfer status updated to {new_status}.')
        else:
            messages.error(request, 'Invalid status.')
    
    return redirect('stock_transfer_detail', transfer_id=transfer.id)

@login_required
def stock_transfer_detail(request, transfer_id):
    """View stock transfer details"""
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    return render(request, 'stock/stock_transfer_detail.html', {'transfer': transfer})

@login_required
def approved_transfer_requests_api(request):
    """API for approved transfer requests"""
    approved_requests = TransferRequest.objects.filter(
        status='approved'
    ).select_related('from_store', 'to_store').prefetch_related('items')
    
    requests_data = []
    for req in approved_requests:
        requests_data.append({
            'id': req.id,
            'from_store': req.from_store.name,
            'to_store': req.to_store.name,
            'items_count': req.items.count(),
            'requested_by': req.requested_by.username,
            'approved_date': req.approved_date.isoformat() if req.approved_date else None,
        })
    
    return JsonResponse({'requests': requests_data})

@login_required
def approved_transfer_requests_json(request):
    """JSON endpoint for approved transfer requests (for modal)"""
    approved_requests = TransferRequest.objects.filter(
        status='approved'
    ).select_related('from_store', 'to_store').prefetch_related('items').order_by('-approved_date')
    
    requests_data = []
    for req in approved_requests:
        requests_data.append({
            'id': req.id,
            'from_store_name': req.from_store.name,
            'to_store_name': req.to_store.name,
            'items_count': req.items.count(),
            'priority': getattr(req, 'priority', 'normal'),
            'approved_date': req.approved_date.isoformat() if req.approved_date else None,
            'note': req.note or '',
        })
    
    return JsonResponse({'requests': requests_data})

@login_required
def create_transfer_from_request(request, request_id):
    """Create a stock transfer from an approved transfer request"""
    transfer_request = get_object_or_404(TransferRequest, id=request_id, status='approved')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                stock_transfer = StockTransfer.objects.create(
                    transfer_request=transfer_request,
                    from_store=transfer_request.from_store,
                    to_store=transfer_request.to_store,
                    created_by=request.user,
                    note=f"Created from approved request #{transfer_request.id}",
                    status='pending'
                )
                
                for request_item in transfer_request.items.all():
                    StockTransferItem.objects.create(
                        stock_transfer=stock_transfer,
                        product=request_item.product,
                        quantity=request_item.quantity,
                        units=request_item.units,
                        transfer_request_item=request_item
                    )
                
                transfer_request.status = 'fulfilled'
                transfer_request.save()
                
                # If this was an AJAX call, return JSON so the frontend can update without a redirect
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'success': True, 'transfer_id': stock_transfer.id}, status=201)

                messages.success(request, f'Stock transfer #{stock_transfer.id} created successfully from request #{transfer_request.id}.')
                return redirect('stock_transfer_detail', transfer_id=stock_transfer.id)
                
        except Exception as e:
            # For AJAX callers return a JSON error
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': False, 'error': str(e)}, status=500)

            messages.error(request, f'Error creating transfer: {str(e)}')
            return redirect('transfer_request_detail', request_id=request_id)
    
    return render(request, 'stock/transfer_from_request_confirm.html', {
        'transfer_request': transfer_request
    })



@login_required
def create_bulk_transfers(request):
    """Create multiple transfers from selected approved requests"""
    if request.method == 'POST':
        selected_request_ids = request.POST.getlist('request_ids')
        
        if not selected_request_ids:
            messages.error(request, 'No transfer requests selected.')
            return redirect('stock_transfer_list')
        
        created_count = 0
        errors = []
        
        for request_id in selected_request_ids:
            try:
                transfer_request = TransferRequest.objects.get(
                    id=request_id, 
                    status='approved'
                )
                
                with transaction.atomic():
                    if StockTransfer.objects.filter(transfer_request=transfer_request).exists():
                        errors.append(f"Transfer already exists for request #{request_id}")
                        continue
                    
                    stock_transfer = StockTransfer.objects.create(
                        transfer_request=transfer_request,
                        from_store=transfer_request.from_store,
                        to_store=transfer_request.to_store,
                        created_by=request.user,
                        note=f"Bulk created from request #{transfer_request.id}",
                        status='pending'
                    )
                    
                    for request_item in transfer_request.items.all():
                        StockTransferItem.objects.create(
                            stock_transfer=stock_transfer,
                            product=request_item.product,
                            quantity=request_item.quantity,
                            units=request_item.units,
                            transfer_request_item=request_item
                        )
                    
                    transfer_request.status = 'fulfilled'
                    transfer_request.save()
                    created_count += 1
                    
            except TransferRequest.DoesNotExist:
                errors.append(f"Request #{request_id} not found or not approved")
            except Exception as e:
                errors.append(f"Error creating transfer from request #{request_id}: {str(e)}")
        
        if created_count > 0:
            messages.success(request, f'Successfully created {created_count} stock transfer(s).')
        if errors:
            messages.warning(request, f'Some transfers failed: {" | ".join(errors[:5])}')
        # If AJAX caller, return JSON summary
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'success': True, 'created': created_count, 'errors': errors}, status=200)

        return redirect('stock_transfer_list')
    
    return redirect('stock_transfer_list')
    
    

@login_required
def direct_stock_transfer_create(request):
   
    if request.method == 'POST':
                
        try:
            with transaction.atomic():
                
                from_store_id = request.POST.get('from_store')
                to_store_id = request.POST.get('to_store')
                note = request.POST.get('note', '')
                status = request.POST.get('status', 'pending')
                
            
                if not from_store_id or not to_store_id:
                    messages.error(request, 'From store and To store are required.')
                    return redirect('stock_transfer_list')
                
          
                try:
                    from_store = StoreLocation.objects.get(id=from_store_id)
                    to_store = StoreLocation.objects.get(id=to_store_id)
                except StoreLocation.DoesNotExist:
                    messages.error(request, 'Invalid store selected.')
                    return redirect('stock_transfer_list')
                
                
                transfer = StockTransfer.objects.create(
                    from_store=from_store,
                    to_store=to_store,
                    note=note,
                    status=status,
                    created_by=request.user, 
                    transfer_request=None    
                )
                
            
                total_forms = int(request.POST.get('items-TOTAL_FORMS', 0))
                items_created = 0
                
                for i in range(total_forms):
                    product_id = request.POST.get(f'items-{i}-product')
                    quantity = request.POST.get(f'items-{i}-quantity')
                    unit_id = request.POST.get(f'items-{i}-units')
                        
                    if product_id and quantity and unit_id:
                        try:
                            product = Product.objects.get(id=product_id)
                            unit = UnitOfMeasure.objects.get(id=unit_id)
                            quantity = int(quantity)
                            
                            if quantity > 0:
                                StockTransferItem.objects.create(
                                    stock_transfer=transfer,
                                    product=product,
                                    quantity=quantity,
                                    units=unit
                                )
                                items_created += 1
                                print(f'✓ Item {items_created} created: {product.name}')
                                
                        except (Product.DoesNotExist, UnitOfMeasure.DoesNotExist, ValueError) as e:
                            print(f'✗ Error creating item {i}: {e}')
                            continue
                
                if items_created > 0:
                    messages.success(request, f'Transfer #{transfer.id} created successfully with {items_created} items!')

                    return redirect('stock_transfer_detail', transfer_id=transfer.id)
                else:
                    transfer.delete()
                    messages.error(request, 'No valid items were added. Transfer cancelled.')
                    print('FAILED: No items created, transfer deleted')
                    return redirect('stock_transfer_list')
                    
        except Exception as e:
            print(f'ERROR DURING TRANSFER CREATION: {str(e)}')
            import traceback
            traceback.print_exc()
            messages.error(request, f'Error creating transfer: {str(e)}')
        
       
    
    return redirect('stock_transfer_list')


@login_required
def start_stock_transfer(request, transfer_id):
    """Mark a transfer as in transit"""
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    
    if transfer.status != 'pending':
        messages.error(request, 'Only pending transfers can be started.')
        return redirect('stock_transfer_detail', transfer_id=transfer.id)
    
    stock_issues = []
    for item in transfer.items.all():
        try:
            inventory = Inventory.objects.get(
                product=item.product, 
                store=transfer.from_store
            )
            if inventory.quantity_in_stock < item.quantity:
                stock_issues.append(
                    f"{item.product.name}: Available {inventory.quantity_in_stock}, Required {item.quantity}"
                )
        except Inventory.DoesNotExist:
            stock_issues.append(f"{item.product.name}: No inventory found")
    
    if stock_issues:
        messages.error(request, f'Insufficient stock: {", ".join(stock_issues)}')
        return redirect('stock_transfer_detail', transfer_id=transfer.id)
    
    transfer.status = 'in_transit'
    transfer.save()
    
    messages.success(request, f'Stock transfer #{transfer.id} marked as in transit.')
    return redirect('stock_transfer_detail', transfer_id=transfer.id)

@login_required
def complete_stock_transfer(request, transfer_id):
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    
    if transfer.status != 'in_transit':
        messages.error(request, 'Only transfers in transit can be completed.')
        return redirect('stock_transfer_detail', transfer_id=transfer.id)
    
    try:
        transfer.apply_inventory_changes()
        messages.success(request, f'Stock transfer #{transfer.id} completed successfully.')
    except ValidationError as e:
        messages.error(request, f'Error completing transfer: {str(e)}')
    except Exception as e:
        messages.error(request, f'Unexpected error: {str(e)}')
    
    return redirect('stock_transfer_detail', transfer_id=transfer.id)



@login_required
def get_product_stock_info(request):
    """JSON endpoint for real-time stock with committed stock calculation"""
    product_id = request.GET.get('product_id')
    store_id = request.GET.get('store_id')
    
    print(f"🔍 DEBUG: Fetching stock for product {product_id}, store {store_id}")
    
    if not product_id or not store_id:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        # Simple query without select_related/only conflict
        inventory = Inventory.objects.get(
            product_id=product_id,
            store_id=store_id
        )
        
        print(f"📊 DEBUG: Base inventory found: {inventory.quantity_in_stock}")
        
        # Calculate committed stock (stock reserved for pending/in-transit transfers)
        # Use lazy import to avoid circular imports
        from app.models.transactions import StockTransferItem
        from django.db.models import Sum
        
        committed_stock = StockTransferItem.objects.filter(
            product_id=product_id,
            stock_transfer__from_store_id=store_id,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
        print(f"🔄 DEBUG: Committed stock: {committed_stock}")
        
        # Calculate truly available stock
        available_stock = max(0, inventory.quantity_in_stock - committed_stock)
        
        print(f"🎯 DEBUG: Available stock: {available_stock} (Base: {inventory.quantity_in_stock} - Committed: {committed_stock})")
        
        response_data = {
            'available_stock': available_stock,
            'total_stock': inventory.quantity_in_stock,
            'committed_stock': committed_stock,
            'reorder_level': inventory.reorder_level,
            'can_fulfill': available_stock > 0,
        }
        
        return JsonResponse(response_data)
        
    except Inventory.DoesNotExist:
        print(f"❌ DEBUG: No inventory record found for product {product_id} in store {store_id}")
        return JsonResponse({
            'available_stock': 0,
            'total_stock': 0,
            'committed_stock': 0,
            'reorder_level': 0,
            'can_fulfill': False,
        })
        
    except Exception as e:
        print(f"💥 DEBUG: Error in get_product_stock_info: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'error': 'Unable to fetch stock information',
            'available_stock': 0,
            'total_stock': 0,
            'committed_stock': 0,
            'can_fulfill': False
        }, status=500)

@login_required
def transfer_request_list(request):
    """List all transfer requests"""
    requests = TransferRequest.objects.all().order_by('-request_date')
    return render(request, 'stock/transfer_request_list.html', {'transfer_requests': requests})

@login_required
def create_transfer_request(request):
    """Create a new transfer request"""
    if request.method == 'POST':
        form = TransferRequestForm(request.POST)
        formset = TransferRequestItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            transfer_request = form.save(commit=False)
            transfer_request.requested_by = request.user
            transfer_request.save()
            
            formset.instance = transfer_request
            formset.save()
            # If AJAX (JSON) request, return JSON response for modal submission
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': True, 'request_id': transfer_request.id})

            messages.success(request, 'Transfer request created successfully.')
            return redirect('transfer_request_detail', request_id=transfer_request.id)
        else:
            # Form or formset invalid
            # If this was an AJAX request (modal submit), return JSON with errors instead of rendering a full template
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                # Collect form and formset errors
                errors = {
                    'form_errors': form.errors or {},
                    'formset_errors': formset.errors or [],
                }
                # include non-field errors if present
                if hasattr(form, 'non_field_errors'):
                    nf = form.non_field_errors()
                    if nf:
                        errors['non_field_errors'] = nf
                return JsonResponse({'success': False, 'errors': errors}, status=400)
    else:
        form = TransferRequestForm()
        formset = TransferRequestItemFormSet()
    
    return render(request, 'stock/transfer_request_form.html', {
        'form': form,
        'formset': formset
    })

@login_required
def transfer_request_detail(request, request_id):
    """View transfer request details"""
    transfer_request = get_object_or_404(TransferRequest, id=request_id)
    return render(request, 'stock/transfer_request_detail.html', {'transfer_request': transfer_request})


@login_required
def transfer_request_json(request, request_id):
    """Return transfer request data and items as JSON (for modal edit)"""
    tr = get_object_or_404(TransferRequest, id=request_id)
    items = []
    for it in tr.items.all():
        items.append({
            'id': it.id,
            'product_id': it.product.id,
            'product_name': it.product.name,
            'quantity': it.quantity,
            'units_id': it.units.id,
            'units_name': it.units.name,
            'notes': getattr(it, 'notes', '')
        })

    data = {
        'id': tr.id,
        'from_store': tr.from_store.id,
        'from_store_name': tr.from_store.name,
        'to_store': tr.to_store.id,
        'to_store_name': tr.to_store.name,
        'priority': getattr(tr, 'priority', 'normal'),
        'required_date': getattr(tr, 'required_date', None) and getattr(tr, 'required_date').isoformat() or None,
        'department': tr.department.id if tr.department else '',
        'department_name': tr.department.name if tr.department else '',
        'reason': tr.note or '',
        'status': tr.status,
        'items': items,
    }

    return JsonResponse({'success': True, 'request': data})

@login_required
def edit_transfer_request(request, request_id):
    """Edit a transfer request"""
    transfer_request = get_object_or_404(TransferRequest, id=request_id)
    
    if request.method == 'POST':
        form = TransferRequestForm(request.POST, instance=transfer_request)
        formset = TransferRequestItemFormSet(request.POST, instance=transfer_request)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            # If AJAX, return JSON for modal callers
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': True, 'request_id': transfer_request.id})

            messages.success(request, 'Transfer request updated successfully.')
            return redirect('transfer_request_detail', request_id=transfer_request.id)
        else:
            # Invalid form/formset
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                errors = {
                    'form_errors': form.errors or {},
                    'formset_errors': formset.errors or [],
                }
                if hasattr(form, 'non_field_errors'):
                    nf = form.non_field_errors()
                    if nf:
                        errors['non_field_errors'] = nf
                return JsonResponse({'success': False, 'errors': errors}, status=400)
    else:
        form = TransferRequestForm(instance=transfer_request)
        formset = TransferRequestItemFormSet(instance=transfer_request)
    
    return render(request, 'stock/transfer_request_form.html', {
        'form': form,
        'formset': formset,
        'transfer_request': transfer_request
    })

@login_required
def update_transfer_request(request, request_id):

    transfer_request = get_object_or_404(TransferRequest, id=request_id)
    
    if request.method == 'POST':
        form = TransferRequestForm(request.POST, instance=transfer_request)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transfer request updated successfully.')
            return redirect('transfer_request_detail', request_id=transfer_request.id)
    
    return redirect('transfer_request_detail', request_id=request_id)

# approve_transfer_request and reject_transfer_request moved to transfer_views.py
# to avoid duplicate function definitions

@login_required
def pending_transfer_requests_for_approval(request):
    pending_requests = TransferRequest.objects.filter(status='pending').order_by('-request_date')
    return render(request, 'stock/pending_transfer_requests.html', {'pending_requests': pending_requests})






# @login_required
# def stock_transfer_list(request):
#     transfers = get_all_stock_transfers()
#     return render(request, 'stock_transfer_list.html', {'transfers': transfers})

# @login_required
# def stock_transfer_detail(request, transfer_id):
#     transfer = get_stock_transfer_by_id(transfer_id)
#     return render(request, 'stock_transfer_detail.html', {'transfer': transfer})

# @login_required
# def create_stock_transfer(request):
#     if request.method == 'POST':
#         form = StockTransferForm(request.POST)
#         if form.is_valid():
#             form.save()
#             messages.success(request, 'Stock transfer recorded successfully.')
#             return redirect('stock_transfer_list')
#     else:
#         form = StockTransferForm()
#     return render(request, 'stock_transfer_form.html', {'form': form})

# @login_required
# def edit_stock_transfer(request, transfer_id):
#     transfer = get_object_or_404(StockTransfer, id=transfer_id)
#     if request.method == 'POST':
#         form = StockTransferForm(request.POST, instance=transfer)
#         if form.is_valid():
#             form.save()
#             messages.success(request, 'Stock transfer updated successfully.')
#             return redirect('stock_transfer_list')
#     else:
#         form = StockTransferForm(instance=transfer)
#     return render(request, 'stock_transfer_form.html', {'form': form, 'transfer': transfer})

# @login_required
# def delete_stock_transfer(request, transfer_id):
#     transfer = get_object_or_404(StockTransfer, id=transfer_id)
#     if request.method == 'POST':
#         transfer.delete()
#         messages.success(request, 'Stock transfer deleted successfully.')
#         return redirect('stock_transfer_list')
#     return render(request, 'stock_transfer_confirm_delete.html', {'transfer': transfer})




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
    
    # Calculate quantities correctly - use MOVEMENT data as source of truth for what actually happened
    record_was_edited = False
    actual_quantity_change = None
    
    if adjustment.status == 'applied' and stock_movements.exists():
        # If applied, use stock movement as the source of truth for what actually happened
        # Movement records are immutable audit trail - they show what was actually applied
        movement = stock_movements.first()
        
        # Movement shows what actually happened:
        # - movement.quantity = the quantity that was actually changed (immutable audit trail)
        # - movement.units_in_stock = stock level AFTER this adjustment was applied
        actual_quantity_change = movement.quantity  # What was actually applied
        quantity_after_actual = movement.units_in_stock  # Stock after this adjustment
        
        # Calculate what stock was BEFORE this adjustment
        quantity_before = quantity_after_actual - actual_quantity_change
        
        # Ensure quantity_before is not negative (safety check)
        if quantity_before < 0:
            quantity_before = 0
        
        # Use movement data (what actually happened) as source of truth
        quantity_after = quantity_after_actual
        
        # Check if adjustment record was edited after application
        record_was_edited = (actual_quantity_change != adjustment.quantity_change)
    elif adjustment.status == 'pending':
        # For pending adjustments, show projected values based on current stock
        quantity_before = current_quantity
        # Projected after = current + change (ensure not negative)
        quantity_after = max(0, current_quantity + adjustment.quantity_change)
    else:
        # For other statuses (approved, cancelled), show current stock only
        quantity_before = None
        quantity_after = current_quantity
    
    # Calculate total value - use actual quantity if available, otherwise use adjustment quantity
    total_value = None
    qty_for_value = actual_quantity_change if actual_quantity_change is not None else adjustment.quantity_change
    if adjustment.unit_cost and qty_for_value:
        # Use absolute value of quantity change for value calculation
        total_value = abs(qty_for_value) * adjustment.unit_cost
    
    context = {
        'adjustment': adjustment,
        'related_adjustments': related_adjustments,
        'batch_totals': batch_totals,
        'stock_movements': stock_movements,
        'current_quantity': current_quantity,
        'quantity_before': quantity_before,
        'quantity_after': quantity_after,
        'total_value': total_value,
        'record_was_edited': record_was_edited,
        'actual_quantity_change': actual_quantity_change,
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
        else:
            # Form is invalid, re-render with errors
            return render(request, 'transactions/stock_adjustment_form.html', {
                'form': form,
                'formset': formset
            })
    
    else:  # GET request - THIS WAS MISSING!
        form = StockAdjustmentForm()
        formset = StockAdjustmentItemFormSet()
        return render(request, 'stock/stock_adjustment_form.html', {
            'form': form,
            'formset': formset
        })
        
        
@login_required
def edit_stock_adjustment(request, adjustment_id):
    adjustment = get_object_or_404(StockAdjustment, id=adjustment_id)
    
    # Prevent editing applied adjustments to maintain audit trail integrity
    if adjustment.status == 'applied':
        messages.warning(request, 'Cannot edit applied adjustments. The adjustment has already been applied to inventory. Editing would create data inconsistencies.')
        return redirect('stock_adjustment_detail', adjustment_id=adjustment.id)
    
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
