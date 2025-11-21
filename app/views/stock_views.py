from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from app.models.transactions import *
from app.forms.transaction_forms import *
from app.selectors.transaction_selectors import (
    get_all_stock_movements, get_stock_movements_by_branch,
    get_all_stock_transfers, get_stock_transfer_by_id, get_stock_transfers_by_branch,
    get_all_orders, get_order_by_id, get_orders_by_branch,
    get_items_by_order
)
from app.models.products import *
from app.forms.transaction_forms import StockAdjustmentItemFormSet

# Added imports for bulk upload
import csv
import io, json
from decimal import Decimal
from datetime import *

from django.http import JsonResponse

from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
from django.db import transaction



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
    """Enhanced stock transfer list view with filtering and statistics"""
    try:
        # Get filter parameters
        status_filter = request.GET.get('status', 'all')
        page_number = request.GET.get('page', 1)
        
        # Base queryset
        transfers = StockTransfer.objects.select_related(
            'from_store', 'to_store', 'transfer_request', 'created_by'
        ).prefetch_related('items__product').all().order_by('-transfer_date')
        
        # Apply status filter
        if status_filter != 'all':
            transfers = transfers.filter(status=status_filter)
        
        # Calculate statistics
        today = timezone.now().date()
        
        # Status counts for all transfers
        status_counts = {
            'pending': StockTransfer.objects.filter(status='pending').count(),
            'in_transit': StockTransfer.objects.filter(status='in_transit').count(),
            'completed': StockTransfer.objects.filter(status='completed').count(),
            'cancelled': StockTransfer.objects.filter(status='cancelled').count(),
        }
        
        # Count approved requests waiting for transfer creation
        pending_approved_requests = TransferRequest.objects.filter(
            status='approved'
        ).count()
        
        # FIXED: Calculate total value of active transfers (pending + in_transit)
        active_transfers = transfers.filter(status__in=['pending', 'in_transit'])
        total_value = Decimal('0.00')
        
        for transfer in active_transfers:
            for item in transfer.items.all():
                try:
                    # Try multiple ways to get the product cost
                    product_cost = Decimal('0.00')
                    
                    # Method 1: Use product's default_price
                    if item.product.default_price:
                        product_cost = Decimal(str(item.product.default_price))
                    # Method 2: Try to get from inventory batches
                    else:
                        batch = InventoryBatch.objects.filter(
                            product=item.product,
                            store=transfer.from_store
                        ).order_by('-created_at').first()
                        if batch and batch.unit_cost:
                            product_cost = Decimal(str(batch.unit_cost))
                    
                    total_value += Decimal(str(item.quantity)) * product_cost
                    
                except (AttributeError, ValueError, TypeError) as e:
                    print(f"Error calculating value for item {item.id}: {e}")
                    continue
        
        # Pagination
        paginator = Paginator(transfers, 25)
        page_obj = paginator.get_page(page_number)
        
        # FIXED: Add calculated properties to each transfer for template
        for transfer in page_obj:
            transfer_total = Decimal('0.00')
            for item in transfer.items.all():
                try:
                    product_cost = Decimal('0.00')
                    
                    if item.product.default_price:
                        product_cost = Decimal(str(item.product.default_price))
                    else:
                        batch = InventoryBatch.objects.filter(
                            product=item.product,
                            store=transfer.from_store
                        ).order_by('-created_at').first()
                        if batch and batch.unit_cost:
                            product_cost = Decimal(str(batch.unit_cost))
                    
                    transfer_total += Decimal(str(item.quantity)) * product_cost
                    
                except (AttributeError, ValueError, TypeError) as e:
                    print(f"Error calculating transfer value for item {item.id}: {e}")
                    continue
            
            transfer.total_value = transfer_total
            
            transfer.is_urgent = (
                transfer.status == 'pending' and 
                transfer.transfer_date >= today - timedelta(days=1)
            )
            
            transfer.is_overdue = False
        
       
        
        try:
            # Initialize forms safely
            stock_form = StockTransferForm()
            
            # Ensure store locations exist before setting queryset
            active_stores = StoreLocation.objects.filter(is_active=True)
            if active_stores.exists():
                stock_form.fields['from_store'].queryset = active_stores
                stock_form.fields['to_store'].queryset = active_stores
            else:
                # Fallback if no active stores
                stock_form.fields['from_store'].queryset = StoreLocation.objects.none()
                stock_form.fields['to_store'].queryset = StoreLocation.objects.none()
                
            item_formset = StockTransferItemFormSet()
            
        except Exception as e:
            # If form initialization fails, create empty forms and log the error
            print(f"Form initialization error: {e}")
            stock_form = StockTransferForm()
            item_formset = StockTransferItemFormSet()
        
        context = {
            'transfers': page_obj,
            'status_counts': status_counts,
            'pending_approved_requests': pending_approved_requests,
            'total_value': total_value,  
            'status_filter': status_filter,
            'current_date': today,
            'stock_form': stock_form,
            'item_formset': item_formset,
            'products': Product.objects.filter(is_active=True),
            'units': UnitOfMeasure.objects.all(),
        }
        
        return render(request, 'transfers/stock_transfer_list.html', context)
        
    except Exception as e:
        # Handle any unexpected errors
        print(f"Error in stock_transfer_list: {e}")
        messages.error(request, "An error occurred while loading the stock transfers page.")
        return redirect('dashboard')  # Redirect to a safe page

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
                
                messages.success(request, f'Stock transfer #{stock_transfer.id} created successfully from request #{transfer_request.id}.')
                return redirect('stock_transfer_detail', transfer_id=stock_transfer.id)
                
        except Exception as e:
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
    """Complete a stock transfer and apply inventory changes"""
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
    """JSON endpoint to get available stock for a product in a store"""
    product_id = request.GET.get('product_id')
    store_id = request.GET.get('store_id')
    
    if not product_id or not store_id:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        inventory = Inventory.objects.get(
            product_id=product_id,
            store_id=store_id
        )
        return JsonResponse({
            'available_stock': inventory.quantity_in_stock,
            'reorder_level': inventory.reorder_level
        })
    except Inventory.DoesNotExist:
        return JsonResponse({'available_stock': 0, 'reorder_level': 0})


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
            
            messages.success(request, 'Transfer request created successfully.')
            return redirect('transfer_request_detail', request_id=transfer_request.id)
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
def edit_transfer_request(request, request_id):
    """Edit a transfer request"""
    transfer_request = get_object_or_404(TransferRequest, id=request_id)
    
    if request.method == 'POST':
        form = TransferRequestForm(request.POST, instance=transfer_request)
        formset = TransferRequestItemFormSet(request.POST, instance=transfer_request)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Transfer request updated successfully.')
            return redirect('transfer_request_detail', request_id=transfer_request.id)
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

@login_required
def approve_transfer_request(request, request_id):
    """Approve a transfer request"""
    transfer_request = get_object_or_404(TransferRequest, id=request_id)
    
    if request.method == 'POST':
        transfer_request.status = 'approved'
        transfer_request.approved_by = request.user
        transfer_request.approved_date = timezone.now()
        transfer_request.save()
        
        messages.success(request, 'Transfer request approved successfully.')
    
    return redirect('transfer_request_detail', request_id=request_id)

@login_required
def reject_transfer_request(request, request_id):
    transfer_request = get_object_or_404(TransferRequest, id=request_id)
    
    if request.method == 'POST':
        transfer_request.status = 'rejected'
        transfer_request.approved_by = request.user
        transfer_request.approved_date = timezone.now()
        transfer_request.save()
        
        messages.success(request, 'Transfer request rejected.')
    
    return redirect('transfer_request_detail', request_id=request_id)

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
    formset = StockAdjustmentItemFormSet()

    context = {
        'adjustments': adjustments,
        'form': form,
        'formset': formset,
    }

    return render(request, 'stock/stock_adjustment_list.html', context)

@login_required
def stock_adjustment_detail(request, adjustment_id):
    adjustment = get_object_or_404(StockAdjustment, id=adjustment_id)
    return render(request, 'stock/stock_adjustment_detail.html', {'adjustment': adjustment})

@login_required
def create_stock_adjustment(request):
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        formset = StockAdjustmentItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            adj = form.save(commit=False)
            # prefer to record username; fallback to form value
            try:
                adj.created_by = request.user.username
            except Exception:
                pass
            adj.save()
            formset.instance = adj
            formset.save()
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
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST, instance=adjustment)
        formset = StockAdjustmentItemFormSet(request.POST, instance=adjustment)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Stock adjustment updated successfully.')
            return redirect('stock_adjustment_detail', adjustment_id=adjustment.id)
    else:
        form = StockAdjustmentForm(instance=adjustment)
        formset = StockAdjustmentItemFormSet(instance=adjustment)
    return render(request, 'stock/stock_adjustment_form.html', {'form': form, 'formset': formset, 'adjustment': adjustment})

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
