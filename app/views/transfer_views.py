# app/views/transfers.py
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.db.models import Sum
import json
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import *
from app.models.transactions import *
from app.models.human_resource import *
from app.models.products import *
from app.forms.transaction_forms import *
from app.selectors.transfer_selectors import *
from app.selectors.product_selectors import get_stores

@login_required
def transfer_request_list(request):
    requests = get_all_transfer_requests()
    departments = Department.objects.filter(is_active=True)
    stores = StoreLocation.objects.filter(is_active=True)
    units = UnitOfMeasure.objects.all()
    
    # Status counts for cards
    status_counts = {
        'pending': requests.filter(status='pending').count(),
        'approved': requests.filter(status='approved').count(),
        'rejected': requests.filter(status='rejected').count(),
        'in_transit': requests.filter(status='in_transit').count(),
        'completed': requests.filter(status='completed').count(),
    }
    
    # Get filter status from URL
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        requests = requests.filter(status=status_filter)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(requests, 20)
    
    try:
        requests = paginator.page(page)
    except PageNotAnInteger:
        requests = paginator.page(1)
    except EmptyPage:
        requests = paginator.page(paginator.num_pages)
    
    context = {
        'requests': requests,
        'departments': departments,
        'stores': stores,
        'units': units,
        'status_counts': status_counts,
        'current_status': status_filter,
        'form': TransferRequestForm(request=request),
        'formset': TransferRequestItemFormSet(),
    }
    return render(request, 'transfers/transfer_request_list.html', context)

@login_required
def create_transfer_request(request):
    """Handle transfer request creation via AJAX"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate: can't transfer to same store
            if data.get('from_store') == data.get('to_store'):
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot transfer stock to the same store'
                }, status=400)
            
            # Validate required fields
            required_fields = ['from_store', 'to_store', 'reason']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'{field.replace("_", " ").title()} is required'
                    }, status=400)
            
            # Validate items
            if not data.get('items') or len(data['items']) == 0:
                return JsonResponse({
                    'success': False,
                    'error': 'At least one item is required'
                }, status=400)
            
            # Check stock availability for each item
            errors = []
            for i, item in enumerate(data['items']):
                try:
                    product = Product.objects.get(pk=item['product_id'])
                    store = StoreLocation.objects.get(pk=data['from_store'])
                    
                    # Get available stock
                    try:
                        inventory = Inventory.objects.get(product=product, store=store)
                        physical_stock = inventory.quantity_in_stock
                    except Inventory.DoesNotExist:
                        physical_stock = 0
                    
                    # Calculate committed stock
                    committed_stock = StockTransferItem.objects.filter(
                        product=product,
                        stock_transfer__from_store=store,
                        stock_transfer__status__in=['pending', 'in_transit']
                    ).aggregate(committed=Sum('quantity'))['committed'] or 0
                    
                    available_stock = max(0, physical_stock - committed_stock)
                    requested_qty = int(item['quantity'])
                    
                    if requested_qty > available_stock:
                        errors.append(
                            f"Item {i+1} ({product.name}): Requested quantity ({requested_qty}) "
                            f"exceeds available stock ({available_stock}) in {store.name}"
                        )
                except (Product.DoesNotExist, StoreLocation.DoesNotExist):
                    errors.append(f"Item {i+1}: Product or store not found")
            
            if errors:
                return JsonResponse({
                    'success': False,
                    'error': 'Stock validation failed',
                    'details': errors
                }, status=400)
            
            # Create transfer request
            with transaction.atomic():
                transfer_request = TransferRequest.objects.create(
                    requested_by=request.user,
                    from_store_id=data['from_store'],
                    to_store_id=data['to_store'],
                    department_id=data.get('department'),
                    priority=data.get('priority', 'normal'),
                    required_date=data.get('required_date'),
                    note=data.get('reason'),
                    status='pending'
                )
                
                # Create items
                for item in data['items']:
                    TransferRequestItem.objects.create(
                        transfer_request=transfer_request,
                        product_id=item['product_id'],
                        quantity=item['quantity'],
                        units_id=item['units_id'],
                        notes=item.get('notes', '')
                    )
            
            return JsonResponse({
                'success': True,
                'request_id': transfer_request.id,
                'message': 'Transfer request created successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@login_required
@csrf_exempt
def update_transfer_request(request, request_id):
    """Update transfer request via AJAX"""
    if request.method == 'POST':
        try:
            transfer_request = TransferRequest.objects.get(pk=request_id, requested_by=request.user)
            
            # Only allow editing if status is pending
            if transfer_request.status != 'pending':
                return JsonResponse({
                    'success': False, 
                    'error': 'Cannot edit transfer request that is not pending.'
                })
            
            data = json.loads(request.body)
            
            # Validate: can't transfer to same store
            if data.get('from_store') == data.get('to_store'):
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot transfer stock to the same store'
                }, status=400)
            
            # Validate required fields
            required_fields = ['from_store', 'to_store', 'reason']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'{field.replace("_", " ").title()} is required'
                    }, status=400)
            
            # Validate items
            if not data.get('items') or len(data['items']) == 0:
                return JsonResponse({
                    'success': False,
                    'error': 'At least one item is required'
                }, status=400)
            
            # Check stock availability for each item
            errors = []
            for i, item in enumerate(data['items']):
                try:
                    product = Product.objects.get(pk=item['product_id'])
                    store = StoreLocation.objects.get(pk=data['from_store'])
                    
                    # Get available stock plus already allocated for this request
                    try:
                        inventory = Inventory.objects.get(product=product, store=store)
                        physical_stock = inventory.quantity_in_stock
                    except Inventory.DoesNotExist:
                        physical_stock = 0
                    
                    # Calculate committed stock excluding this request's items
                    committed_stock = StockTransferItem.objects.filter(
                        product=product,
                        stock_transfer__from_store=store,
                        stock_transfer__status__in=['pending', 'in_transit']
                    ).exclude(
                        stock_transfer__transfer_request=transfer_request
                    ).aggregate(committed=Sum('quantity'))['committed'] or 0
                    
                    available_stock = max(0, physical_stock - committed_stock)
                    requested_qty = int(item['quantity'])
                    
                    if requested_qty > available_stock:
                        errors.append(
                            f"Item {i+1} ({product.name}): Requested quantity ({requested_qty}) "
                            f"exceeds available stock ({available_stock}) in {store.name}"
                        )
                except (Product.DoesNotExist, StoreLocation.DoesNotExist):
                    errors.append(f"Item {i+1}: Product or store not found")
            
            if errors:
                return JsonResponse({
                    'success': False,
                    'error': 'Stock validation failed',
                    'details': errors
                }, status=400)
            
            # Update transfer request
            with transaction.atomic():
                transfer_request.from_store_id = data['from_store']
                transfer_request.to_store_id = data['to_store']
                transfer_request.department_id = data.get('department')
                transfer_request.priority = data.get('priority', 'normal')
                transfer_request.required_date = data.get('required_date')
                transfer_request.note = data.get('reason')
                transfer_request.save()
                
                # Delete existing items
                transfer_request.items.all().delete()
                
                # Create new items
                for item in data['items']:
                    TransferRequestItem.objects.create(
                        transfer_request=transfer_request,
                        product_id=item['product_id'],
                        quantity=item['quantity'],
                        units_id=item['units_id'],
                        notes=item.get('notes', '')
                    )
            
            return JsonResponse({
                'success': True,
                'request_id': transfer_request.id,
                'message': 'Transfer request updated successfully'
            })
            
        except TransferRequest.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Transfer request not found'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@login_required
def transfer_request_detail(request, request_id):
    transfer_request = get_object_or_404(TransferRequest, pk=request_id)
    form = TransferRequestForm(instance=transfer_request)
    request_items = transfer_request.items.all()

    context = {
        'request': transfer_request,
        'form': form, 
        'items': request_items,
    }

    return render(request, 'transfers/transfer_request_details.html', context)

@login_required
def get_product_units(request, product_id):
    """Get units available for a specific product"""
    try:
        product = Product.objects.get(pk=product_id)
        units = product.unit_prices.all().select_related('unit')
        
        units_data = [
            {
                'id': unit.unit.id,
                'name': unit.unit.name,
                'abbreviation': unit.unit.abbreviation,
                'conversion_factor': unit.conversion_factor,
                'price': float(unit.price)
            }
            for unit in units
        ]
        
        return JsonResponse({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'sku': product.sku
            },
            'units': units_data
        })
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def get_product_stock_for_store(request, product_id, store_id):
    """Get real-time stock for a product in a specific store"""
    try:
        product = Product.objects.get(pk=product_id)
        store = StoreLocation.objects.get(pk=store_id)
        
        # Get inventory
        try:
            inventory = Inventory.objects.get(product=product, store=store)
            physical_stock = inventory.quantity_in_stock
        except Inventory.DoesNotExist:
            physical_stock = 0
        
        # Calculate committed stock (pending/in-transit transfers)
        committed_stock = StockTransferItem.objects.filter(
            product=product,
            stock_transfer__from_store=store,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
        available_stock = max(0, physical_stock - committed_stock)
        
        return JsonResponse({
            'success': True,
            'stock': {
                'physical_stock': physical_stock,
                'committed_stock': committed_stock,
                'available_stock': available_stock,
                'reorder_level': inventory.reorder_level if 'inventory' in locals() else 0
            },
            'product': {
                'id': product.id,
                'name': product.name,
                'sku': product.sku
            },
            'store': {
                'id': store.id,
                'name': store.name
            }
        })
    except (Product.DoesNotExist, StoreLocation.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Product or Store not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def get_product_unit_price(request, product_id, unit_id):
    """Get price for a specific product unit"""
    try:
        unit_price = ProductUnitPrice.objects.get(product_id=product_id, unit_id=unit_id)
        
        return JsonResponse({
            'success': True,
            'unit_price': {
                'id': unit_price.id,
                'product_id': unit_price.product_id,
                'unit_id': unit_price.unit_id,
                'unit_name': unit_price.unit.name,
                'price': float(unit_price.price),
                'conversion_factor': unit_price.conversion_factor
            }
        })
    except ProductUnitPrice.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unit price not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def transfer_request_json(request, request_id):
    """Get transfer request data in JSON format for editing"""
    try:
        transfer_request = TransferRequest.objects.get(pk=request_id)
        
        # Check permissions
        if not (request.user.is_superuser or transfer_request.requested_by == request.user):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        items_data = []
        for item in transfer_request.items.all().select_related('product', 'units'):
            items_data.append({
                'id': item.id,
                'product_id': item.product_id,
                'product_name': item.product.name,
                'product_sku': item.product.sku,
                'quantity': item.quantity,
                'units_id': item.units_id,
                'units_name': item.units.name if item.units else None,
                'notes': item.notes if hasattr(item, 'notes') else ''
            })
        
        return JsonResponse({
            'success': True,
            'request': {
                'id': transfer_request.id,
                'from_store': transfer_request.from_store_id,
                'to_store': transfer_request.to_store_id,
                'priority': transfer_request.priority,
                'required_date': transfer_request.required_date.strftime('%Y-%m-%d') if transfer_request.required_date else None,
                'department': transfer_request.department_id,
                'reason': transfer_request.reason if hasattr(transfer_request, 'reason') else transfer_request.note,
                'status': transfer_request.status,
                'items': items_data
            }
        })
    except TransferRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transfer request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def stock_transfer_list(request):
    # Delegate to the canonical stock_transfer_list implementation in app.views.transfers
    from app.views.transfers import stock_transfer_list as canonical_stock_transfer_list
    return canonical_stock_transfer_list(request)

@login_required
def stock_transfer_create(request):
    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        formset = StockTransferItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            transfer = form.save()
            formset.instance = transfer
            formset.save()
           
            messages.success(request, 'Stock transfer created successfully.')
            
        return redirect(stock_transfer_list)

@login_required
def stock_transfer_detail(request, pk):
    transfer_obj = get_stock_transfer_by_id(pk)
    if not transfer_obj:
        return render(request, '404.html', status=404)
    return render(request, 'transfers/stock_transfer_detail.html', {'transfer_obj': transfer_obj})

@login_required
def stock_transfer_update(request, pk):
    transfer = get_object_or_404(StockTransfer, pk=pk)
    if request.method == 'POST':
        form = StockTransferForm(request.POST, instance=transfer)
        formset = StockTransferItemFormSet(request.POST, instance=transfer)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Stock transfer updated successfully.')
            return redirect('stock_transfer_list')
    else:
        form = StockTransferForm(instance=transfer)
        formset = StockTransferItemFormSet(instance=transfer)
    return render(request, 'stock_transfer_form.html', {'form': form, 'item_formset': formset})

@login_required
def pending_transfer_requests_for_approval(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('index_page')
    
    requests = get_pending_transfer_requests()
    approval_form = TransferRequestApprovalForm()

    context = {
        'requests': requests,
        'approval_form': approval_form
    }
    return render(request, 'transfers/pending_transfer_requests.html', context)

@login_required
def approve_transfer_request(request, request_id):
    """Approve a transfer request with optional comments - handles AJAX from list page"""
    from django.utils import timezone
    
    try:
        # Only allow POST method
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Only POST method allowed'}, status=405)
        
        try:
            transfer_request = TransferRequest.objects.get(pk=request_id)
        except TransferRequest.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Transfer request not found'}, status=404)
        
        # Validate that request is in pending status
        if transfer_request.status != 'pending':
            error_msg = f'Cannot approve request. Current status is: {transfer_request.get_status_display()}'
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
        
        # Update status and approver info
        transfer_request.status = 'approved'
        transfer_request.approved_by = request.user
        transfer_request.approved_date = timezone.now()
        
        # Save comments if provided
        comments = request.POST.get('comments', '').strip()
        if comments:
            existing_note = transfer_request.note or ''
            approval_note = f"[Approved by {request.user.get_full_name() or request.user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}]: {comments}"
            transfer_request.note = f"{existing_note}\n{approval_note}".strip() if existing_note else approval_note
        
        transfer_request.save()

        # Always return JSON for POST requests (AJAX from list page)
        return JsonResponse({
            'success': True,
            'request_id': transfer_request.id,
            'message': 'Transfer request approved successfully. It now appears in the Approved Requests list.'
        })
    except Exception as e:
        # Catch any unexpected errors and return JSON
        import traceback
        print(f"Error in approve_transfer_request: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'}, status=500)

@login_required
def reject_transfer_request(request, request_id):
    """Reject a transfer request with optional comments - handles AJAX from list page"""
    from django.utils import timezone
    
    try:
        # Only allow POST method
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Only POST method allowed'}, status=405)
        
        try:
            transfer_request = TransferRequest.objects.get(pk=request_id)
        except TransferRequest.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Transfer request not found'}, status=404)
        
        # Validate that request is in pending status
        if transfer_request.status != 'pending':
            error_msg = f'Cannot reject request. Current status is: {transfer_request.get_status_display()}'
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
        
        # Update status and approver info
        transfer_request.status = 'rejected'
        transfer_request.approved_by = request.user
        transfer_request.approved_date = timezone.now()
        
        # Save comments if provided
        comments = request.POST.get('comments', '').strip()
        if comments:
            existing_note = transfer_request.note or ''
            rejection_note = f"[Rejected by {request.user.get_full_name() or request.user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}]: {comments}"
            transfer_request.note = f"{existing_note}\n{rejection_note}".strip() if existing_note else rejection_note
        
        transfer_request.save()

        # Always return JSON for POST requests (AJAX from list page)
        return JsonResponse({
            'success': True, 
            'request_id': transfer_request.id,
            'message': 'Transfer request rejected.'
        })
    except Exception as e:
        # Catch any unexpected errors and return JSON
        import traceback
        print(f"Error in reject_transfer_request: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'}, status=500)



# views.py - add this function
@login_required
def product_stock_calculation(request, product_id):
    """Calculate available stock after considering requested quantity"""
    try:
        product = Product.objects.get(pk=product_id)
        store_id = request.GET.get('store_id')
        requested_qty = int(request.GET.get('requested_qty', 0))
        
        if not store_id:
            return JsonResponse({'success': False, 'error': 'Store ID is required'}, status=400)
        
        store = StoreLocation.objects.get(pk=store_id)
        
        # Get current inventory
        try:
            inventory = Inventory.objects.get(product=product, store=store)
            physical_stock = inventory.quantity_in_stock
        except Inventory.DoesNotExist:
            physical_stock = 0
        
        # Calculate committed stock (excluding this request if editing)
        committed_stock = StockTransferItem.objects.filter(
            product=product,
            stock_transfer__from_store=store,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
        # Get current request items being edited (if any)
        current_request_id = request.GET.get('current_request_id')
        if current_request_id:
            try:
                current_request = TransferRequest.objects.get(pk=current_request_id)
                # Exclude this request's items from committed stock
                current_request_items = TransferRequestItem.objects.filter(
                    transfer_request=current_request,
                    product=product
                ).aggregate(total=Sum('quantity'))['total'] or 0
                committed_stock = max(0, committed_stock - current_request_items)
            except TransferRequest.DoesNotExist:
                pass
        
        # Calculate available stock
        available_stock = max(0, physical_stock - committed_stock)
        
        # Calculate remaining stock if this quantity is requested
        remaining_stock = max(0, available_stock - requested_qty)
        
        return JsonResponse({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'sku': product.sku
            },
            'store': {
                'id': store.id,
                'name': store.name
            },
            'stock_info': {
                'physical_stock': physical_stock,
                'committed_stock': committed_stock,
                'available_stock': available_stock,
                'requested_quantity': requested_qty,
                'remaining_stock': remaining_stock
            },
            'status': 'sufficient' if requested_qty <= available_stock else 'insufficient'
        })
        
    except (Product.DoesNotExist, StoreLocation.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Product or Store not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



















