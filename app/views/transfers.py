# from django.http import JsonResponse
# from django.shortcuts import render, get_object_or_404, redirect
# from django.contrib.auth.decorators import login_required, permission_required
# from django.views.decorators.http import require_http_methods
# from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator
# from django.views.generic import ListView
# from django.contrib import messages
# from django.db.models import Q, Count, Sum
# from django.core.paginator import Paginator
# from django.utils import timezone
# from datetime import datetime, timedelta
# import json
# from django.db import transaction
# from django.core.exceptions import ValidationError

# from app.forms.transaction_forms import StockTransferForm, StockTransferItemFormSet
# from app.models.transactions import TransferRequest, StockTransfer, StockTransferItem
# from app.models.products import StoreLocation as Store
# from app.selectors.transfer_selectors import *
# from app.selectors.product_selectors import get_stores, get_all_products, get_all_units_of_measurement
# from app.models.products import Inventory



# @login_required
# def stock_transfer_list(request):
#     """Display list of stock transfers with filtering and pagination"""
    
#     # Get filter parameters
#     status_filter = request.GET.get('status', 'all')
#     search = request.GET.get('search', '')
    
#     # Base queryset
#     transfers = StockTransfer.objects.select_related(
#         'from_store', 'to_store', 'transfer_request', 'created_by'
#     ).prefetch_related('items__product')
    
#     # Apply status filter
#     if status_filter and status_filter != 'all':
#         transfers = transfers.filter(status=status_filter)
    
#     # Apply search filter
#     if search:
#         transfers = transfers.filter(
#             Q(id__icontains=search) |
#             Q(from_store__name__icontains=search) |
#             Q(to_store__name__icontains=search) |
#             Q(transfer_request__id__icontains=search)
#         )
    
#     # Order by most recent
#     transfers = transfers.order_by('-transfer_date')
    
#     # Get status counts for dashboard cards
#     status_counts = {
#         'pending': StockTransfer.objects.filter(status='pending').count(),
#         'in_transit': StockTransfer.objects.filter(status='in_transit').count(),
#         'completed': StockTransfer.objects.filter(status='completed').count(),
#         'cancelled': StockTransfer.objects.filter(status='cancelled').count(),
#     }
    
#     # Get pending approved requests count
#     pending_approved_requests = TransferRequest.objects.filter(
#         status='approved',
#         stock_transfers__isnull=True  # Not yet converted to transfer
#     ).count()
    
#     # Calculate total value of active transfers
#     # total_value = StockTransfer.objects.filter(
#     #     status__in=['pending', 'in_transit']
#     # ).aggregate(
#     #     total=Sum('items__quantity') * Sum('items__unit_cost')
#     # )['total'] or 0

#     stock_form = StockTransferForm()
#     item_formset = StockTransferItemFormSet(queryset=StockTransferItem.objects.none(), prefix='items')
#     stores = get_stores()
#     products = get_all_products()
    
#     # Pagination
#     paginator = Paginator(transfers, 25)
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)

#     # Calculate total value of active (non-cancelled) transfers using item.total_value
#     total_value = 0
#     try:
#         from decimal import Decimal
#         total_value = Decimal('0.00')
#         active_qs = transfers.exclude(status='cancelled')
#         for t in active_qs:
#             for item in t.items.all():
#                 try:
#                     iv = item.total_value
#                     if iv is not None:
#                         total_value += Decimal(str(iv))
#                 except Exception:
#                     continue
#     except Exception:
#         total_value = 0
    
#     context = {
#         'transfers': page_obj,
#         'status_counts': status_counts,
#         'pending_approved_requests': pending_approved_requests,
#         'total_values': total_value,
#         'current_status': status_filter,
#         'search_query': search,
#         'stock_form': stock_form,
#         'item_formset': item_formset,
#         'stores': stores,
#         'products': products,
#         'units': get_all_units_of_measurement()
#     }
    
#     return render(request, 'transfers/stock_transfer_list.html', context)


# @login_required
# def stock_transfer_detail(request, transfer_id):
#     """Display detailed view of a specific stock transfer"""
    
#     transfer = get_object_or_404(
#         StockTransfer.objects.select_related(
#             'from_store', 'to_store', 'transfer_request', 'created_by'
#         ).prefetch_related('items__product'),
#         id=transfer_id
#     )
    
#     # Calculate additional properties
#     # transfer.total_quantity = sum(item.quantity for item in transfer.items.all())
#     # transfer.is_overdue = (
#     #     transfer.expected_delivery_date and 
#     #     transfer.expected_delivery_date < timezone.now().date() and
#     #     transfer.status != 'completed'
#     # )
    
#     context = {
#         'transfer': transfer,
#     }
    
#     return render(request, 'transfers/stock_transfer_detail.html', context)


# @login_required
# @require_http_methods(["GET"])
# def approved_transfer_requests_api(request):
#     """API endpoint to fetch approved transfer requests for modal display"""
    
#     # try:
#     # Get approved requests that haven't been converted to transfers yet
#     approved_requests = TransferRequest.objects.filter(
#         status='approved',
#         stock_transfers__isnull=True  # Not yet converted
#     ).select_related(
#         'from_store', 'to_store', 'requested_by', 'approved_by'
#     ).prefetch_related('items').order_by('-approved_date')
    
#     # Serialize the data
#     requests_data = []
#     for request in approved_requests:
#         requests_data.append({
#             'id': request.id,
#             'from_store_name': request.from_store.name,
#             'to_store_name': request.to_store.name,
#             'items_count': request.items.count(),
#             # 'priority': request.priority,
#             'approved_date': request.approved_date.isoformat() if request.approved_date else None,
#             'requested_by': request.requested_by.get_full_name() or request.requested_by.username,
#             'approved_by': request.approved_by.get_full_name() if request.approved_by else None,
#             # 'reason': request.reason or '',
#         })
    
#     return JsonResponse({
#         'success': True,
#         'requests': requests_data,
#         'count': len(requests_data)
#     })
        
#     # except Exception as e:
#     #     return JsonResponse({
#     #         'success': False,
#     #         'error': str(e)
#     #     }, status=500)


# @login_required
# @require_http_methods(["POST"])
# def update_transfer_status(request, transfer_id):
#     """API endpoint to update stock transfer status"""
    
#     try:
#         transfer = get_object_or_404(StockTransfer, id=transfer_id)
        
#         # Parse request data
#         if request.content_type == 'application/json':
#             data = json.loads(request.body)
#         else:
#             data = request.POST
        
#         new_status = data.get('status')
#         comments = data.get('comments', '')
        
#         # Validate status transition
#         valid_transitions = {
#             'pending': ['in_transit', 'cancelled'],
#             'in_transit': ['completed', 'cancelled'],
#             'completed': [],  
#             'cancelled': [],  
#         }
        
#         if new_status not in valid_transitions.get(transfer.status, []):
#             return JsonResponse({
#                 'success': False,
#                 'error': f'Invalid status transition from {transfer.status} to {new_status}'
#             }, status=400)
        
#         # Update transfer status
#         old_status = transfer.status
#         transfer.status = new_status
        
#         # Set appropriate timestamps
#         now = timezone.now()
#         if new_status == 'in_transit':
#             transfer.started_date = now
#             transfer.started_by = request.user
#         elif new_status == 'completed':
#             transfer.completion_date = now
#             transfer.completed_by = request.user
#             # Apply inventory changes 
#             transfer.apply_inventory_changes()
#         elif new_status == 'cancelled':
#             transfer.cancellation_date = now
#             transfer.cancelled_by = request.user
#             transfer.cancellation_reason = data.get('cancellation_reason', comments)
        
#         transfer.save()
        
#         # Log the status change (optional - if you have an audit log)
#         # AuditLog.objects.create(
#         #     user=request.user,
#         #     action=f'Transfer status changed from {old_status} to {new_status}',
#         #     object_id=transfer.id,
#         #     content_type=ContentType.objects.get_for_model(StockTransfer),
#         #     comments=comments
#         # )
        
#         return JsonResponse({
#             'success': True,
#             'message': f'Transfer status updated to {new_status}',
#             'new_status': new_status
#         })
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': str(e)
#         }, status=500)


# @login_required
# def stock_transfer_create(request):
#     """Create a new stock transfer, optionally from an approved request"""
    
#     # Get the request ID if creating from approved request
#     request_id = request.GET.get('request')
#     transfer_request = None
    
#     if request_id:
#         try:
#             transfer_request = get_object_or_404(
#                 TransferRequest,
#                 id=request_id,
#                 status='approved'
#             )
#             # Check if already converted
#             if hasattr(transfer_request, 'stocktransfer'):
#                 messages.warning(request, 'This request has already been converted to a transfer.')
#                 return redirect('stock_transfer_list')
#         except:
#             messages.error(request, 'Invalid or unauthorized transfer request.')
#             return redirect('stock_transfer_list')
    
#     if request.method == 'POST':
#         # Handle form submission
#         stock_form = StockTransferForm(request.POST)
#         item_formset = StockTransferItemFormSet(request.POST)

#         if stock_form.is_valid() and item_formset.is_valid():
#             try:
#             # Create the stock transfer
#                 stock_transfer = stock_form.save(commit=False)
#                 stock_transfer.created_by = request.user
#                 stock_transfer.transfer_request = transfer_request
                
#                 # Set default dates if not provided
#                 if not stock_transfer.transfer_date:
#                     stock_transfer.transfer_date = timezone.now()
                
#                 stock_transfer.save()
                
#                 # Create transfer items
#                 items_created = 0
#                 for form in item_formset:
#                     if form.is_valid() and form.cleaned_data:
#                         # Check if form has data and is not marked for deletion
#                         if not form.cleaned_data.get('DELETE', False):
#                             transfer_item = form.save(commit=False)
#                             transfer_item.stock_transfer = stock_transfer
                            
#                             # Set unit cost from product if not provided
#                             if not transfer_item.unit_cost:
#                                 transfer_item.unit_cost = transfer_item.product.cost_price or 0
                            
#                             # Link to transfer request item if available
#                             if transfer_request:
#                                 try:
#                                     request_item = transfer_request.items.get(
#                                         product=transfer_item.product
#                                     )
#                                     transfer_item.transfer_request_item = request_item
#                                 except:
#                                     pass  # No matching request item found
                            
#                             transfer_item.save()
#                             items_created += 1
                
#                 if items_created == 0:
#                     # No items were created, delete the transfer
#                     stock_transfer.delete()
#                     messages.error(request, 'At least one item must be added to create a transfer.')
#                     return redirect('stock_transfer_list')
                
#                 messages.success(
#                     request, 
#                     f'Stock transfer #{stock_transfer.id} created successfully with {items_created} item(s).'
#                 )
#                 return redirect('stock_transfer_detail', transfer_id=stock_transfer.id)
            
#             except Exception as e:
#                 messages.error(request, f'Error creating transfer: {str(e)}')
        
#         else:
#             # Form validation errors
#             if not stock_form.is_valid():
#                 for field, errors in stock_form.errors.items():
#                     for error in errors:
#                         messages.error(request, f'{field}: {error}')
            
#             if not item_formset.is_valid():
#                 for i, form in enumerate(item_formset):
#                     if form.errors:
#                         for field, errors in form.errors.items():
#                             for error in errors:
#                                 messages.error(request, f'Item {i+1} - {field}: {error}')
    
#     else:
#         # GET request - initialize forms
#         initial_data = {}
        
#         # Pre-populate from transfer request if available
#         if transfer_request:
#             initial_data = {
#                 'from_store': transfer_request.from_store,
#                 'to_store': transfer_request.to_store,
#                 'notes': f'Created from transfer request #{transfer_request.id}',
#                 # 'expected_delivery_date': transfer_request.required_date,
#             }
        
#         stock_form = StockTransferForm(initial=initial_data)
        
#         # Initialize formset with transfer request items if available
#         if transfer_request:
#             initial_items = []
#             for request_item in transfer_request.items.all():
#                 initial_items.append({
#                     'product': request_item.product,
#                     'quantity': request_item.quantity,
#                     'units': request_item.units,
#                     'unit_cost': request_item.product.default_price or 0,
#                 })
            
#             item_formset = StockTransferItemFormSet(initial=initial_items)
#         else:
#             item_formset = StockTransferItemFormSet()
    
#     return redirect('stock_transfer_list')
#     # context = {
#     #     'stock_form': stock_form,
#     #     'item_formset': item_formset,
#     #     'transfer_request': transfer_request,
#     #     'stores': Store.objects.filter(is_active=True),
#     #     'is_create': True,
#     # }
    
#     # return render(request, 'transfers/stock_transfer_form.html')

# @login_required
# def direct_stock_transfer_create(request):
#     """Handle creation of direct stock transfers (without prior request)"""
    
#     if request.method == 'POST':
#         stock_form = StockTransferForm(request.POST)
#         item_formset = StockTransferItemFormSet(request.POST)

#         if stock_form.is_valid() and item_formset.is_valid():
#             try:
#                 with transaction.atomic():
#                     # Create stock transfer
#                     stock_transfer = stock_form.save(commit=False)
#                     stock_transfer.created_by = request.user
#                     stock_transfer.transfer_date = timezone.now()
#                     stock_transfer.save()

#                     # Process items
#                     items_created = 0
#                     validation_errors = []

#                     for form in item_formset:
#                         if form.is_valid() and form.cleaned_data and not form.cleaned_data.get('DELETE'):

#                             # Get the product and quantity first
#                             product = form.cleaned_data.get('product')
#                             quantity = form.cleaned_data.get('quantity')

#                             if not product or not quantity:
#                                 continue

#                             # Create transfer item
#                             transfer_item = form.save(commit=False)
#                             transfer_item.stock_transfer = stock_transfer
                            
#                             # Validate stock
#                             available_stock = get_available_stock(product, stock_transfer.from_store)
#                             if quantity > available_stock:
#                                 validation_errors.append(
#                                     f'Insufficient stock for {product.name}: '
#                                     f'Available: {available_stock}, Requested: {quantity}'
#                                 )
#                                 continue

#                             # # Set unit cost if not provided
#                             # if not transfer_item.unit_cost:
#                             #     transfer_item.unit_cost = product.cost_price or 0

#                             # Save the transfer item
#                             try:
#                                 transfer_item.save()
                               
#                                 items_created += 1
#                             except Exception as e:
#                                 validation_errors.append(f'Error saving item: {str(e)}')
            
#                 if validation_errors:
#                     # If we have validation errors, rollback the transaction
#                     raise ValidationError('\n'.join(validation_errors))
                
#                 if items_created == 0:
#                     # If no items were created, rollback the transaction
#                     raise ValidationError('At least one valid item must be added to create a transfer.',)
#                 # {stock_transfer.id}
#                 messages.success(
#                     request, 
#                     f'Direct stock transfer # created successfully with {items_created} item(s).'
#                 )
#                 return redirect('stock_transfer_list')
                    
#             except ValidationError as e:
#                 messages.error(request, str(e))
#             except Exception as e:
#                 messages.error(request, f'Error creating transfer: {str(e)}')
                
#         else:
#             # Form validation errors
#             for field, errors in stock_form.errors.items():
#                 for error in errors:
#                     messages.error(request, f'{field}: {error}')
            
#             for i, form in enumerate(item_formset):
#                 if form.errors:
#                     for field, errors in form.errors.items():
#                         for error in errors:
#                             messages.error(request, f'Item {i+1} - {field}: {error}')
    
#     # For both GET requests and form validation failures
#     context = {
#         'stock_form': StockTransferForm(),
#         'item_formset': StockTransferItemFormSet(queryset=StockTransferItem.objects.none()),
#         'stores': Store.objects.filter(is_active=True),
#         'products': get_all_products(),
#         'is_direct': True
#     }
    
#     # Return to the list view with the modal context
#     return render(request, 'transfers/stock_transfer_list.html', context)

# def get_available_stock(product, store):
#     """Helper function to get available stock for a product in a store"""
#     try:
#         inventory = Inventory.objects.get(product=product, store=store)
#         return inventory.quantity_in_stock
#     except Inventory.DoesNotExist:
#         return 0

# @login_required
# def stock_transfer_create_bulk(request):
#     """Create multiple stock transfers from selected approved requests"""
    
#     request_ids = request.GET.get('requests', '').split(',')
    
#     if not request_ids or request_ids == ['']:
#         messages.error(request, 'No requests selected.')
#         return redirect('stock_transfer_list')
    
#     try:
#         # Get approved requests
#         approved_requests = TransferRequest.objects.filter(
#             id__in=request_ids,
#             status='approved',
#             stock_transfers__isnull=True  # Not already converted
#         )
        
#         if not approved_requests:
#             messages.error(request, 'No valid requests found for bulk creation.')
#             return redirect('stock_transfer_list')
        
#         if request.method == 'POST':
#             # Create transfers from requests
#             created_count = 0
            
#             for transfer_request in approved_requests:
#                 # Create stock transfer
#                 stock_transfer = StockTransfer.objects.create(
#                     transfer_request=transfer_request,
#                     from_store=transfer_request.from_store,
#                     to_store=transfer_request.to_store,
#                     created_by=request.user,
#                     status='pending'
#                 )
                
#                 # Create transfer items from request items
#                 for request_item in transfer_request.items.all():
#                     StockTransferItem.objects.create(
#                         stock_transfer=stock_transfer,
#                         product=request_item.product,
#                         quantity=request_item.quantity,
#                         unit_cost=request_item.product.cost_price or 0,
#                         units=request_item.units
#                     )
                
#                 created_count += 1
            
#             messages.success(
#                 request, 
#                 f'Successfully created {created_count} stock transfer{"s" if created_count != 1 else ""}.'
#             )
#             return redirect('stock_transfer_list')
        
#         context = {
#             'approved_requests': approved_requests,
#             'request_count': len(request_ids),
#         }
        
#         return redirect('stock_transfer_list')
        
#     except Exception as e:
#         messages.error(request, f'Error creating bulk transfers: {str(e)}')
#         return redirect('stock_transfer_list')


# @login_required
# def stock_transfer_update(request, transfer_id):
#     """Update an existing stock transfer (only if status is pending)"""
    
#     transfer = get_object_or_404(StockTransfer, id=transfer_id)
    
#     if transfer.status != 'pending':
#         messages.error(request, 'Only pending transfers can be edited.')
#         return redirect('stock_transfer_detail', transfer_id=transfer.id)
    
#     if request.method == 'POST':
#         # Handle form submission
#         stock_form = StockTransferForm(request.POST, instance=transfer)
#         item_formset = StockTransferItemFormSet(
#             request.POST, 
#             queryset=transfer.items.all()
#         )
        
#         if stock_form.is_valid() and item_formset.is_valid():
#             try:
#                 # Update the stock transfer
#                 stock_transfer = stock_form.save(commit=False)
#                 stock_transfer.updated_by = request.user
#                 stock_transfer.updated_date = timezone.now()
#                 stock_transfer.save()
                
#                 # Process formset items
#                 items_count = 0
#                 for form in item_formset:
#                     if form.is_valid():
#                         if form.cleaned_data.get('DELETE', False):
#                             # Delete marked items
#                             if form.instance.pk:
#                                 form.instance.delete()
#                         elif form.cleaned_data:
#                             # Save/update items
#                             transfer_item = form.save(commit=False)
#                             transfer_item.stock_transfer = stock_transfer
                            
#                             # Set unit cost from product if not provided
#                             if not transfer_item.unit_cost:
#                                 transfer_item.unit_cost = transfer_item.product.cost_price or 0
                            
#                             transfer_item.save()
#                             items_count += 1
                
#                 if items_count == 0:
#                     messages.error(request, 'At least one item must remain in the transfer.')
#                     return render(request, 'transfers/stock_transfer_form.html', {
#                         'stock_form': stock_form,
#                         'item_formset': item_formset,
#                         'transfer': transfer,
#                         'stores': Store.objects.filter(is_active=True),
#                         'is_create': False,
#                     })
                
#                 messages.success(
#                     request, 
#                     f'Stock transfer #{stock_transfer.id} updated successfully.'
#                 )
#                 return redirect('stock_transfer_detail', transfer_id=stock_transfer.id)
                
#             except Exception as e:
#                 messages.error(request, f'Error updating transfer: {str(e)}')
        
#         else:
#             # Form validation errors
#             if not stock_form.is_valid():
#                 for field, errors in stock_form.errors.items():
#                     for error in errors:
#                         messages.error(request, f'{field}: {error}')
            
#             if not item_formset.is_valid():
#                 for i, form in enumerate(item_formset):
#                     if form.errors:
#                         for field, errors in form.errors.items():
#                             for error in errors:
#                                 messages.error(request, f'Item {i+1} - {field}: {error}')
    
#     else:
#         # GET request - initialize forms with existing data
#         stock_form = StockTransferForm(instance=transfer)
#         item_formset = StockTransferItemFormSet(queryset=transfer.items.all())
    
#     context = {
#         'stock_form': stock_form,
#         'item_formset': item_formset,
#         'transfer': transfer,
#         'stores': Store.objects.filter(is_active=True),
#         'is_create': False,
#     }
    
#     return render(request, 'transfers/stock_transfer_form.html', context)


# # Transfer Request Views (if not already implemented)

# @login_required
# def transfer_request_list(request):
#     """Display list of transfer requests with filtering"""
    
#     status_filter = request.GET.get('status', 'all')
    
#     requests = TransferRequest.objects.select_related(
#         'from_store', 'to_store', 'requested_by'
#     ).prefetch_related('items')
    
#     if status_filter and status_filter != 'all':
#         requests = requests.filter(status=status_filter)
    
#     requests = requests.order_by('-request_date')

#     stores = Store.objects.filter(is_active=True)
    
#     # Calculate status counts for summary cards
#     all_requests = TransferRequest.objects.all()
#     status_counts = {
#         'pending': all_requests.filter(status='pending').count(),
#         'approved': all_requests.filter(status='approved').count(),
#         'in_transit': all_requests.filter(status='approved').count(),  # Using approved as proxy for in_transit
#         'completed': all_requests.filter(status='fulfilled').count(),
#         'rejected': all_requests.filter(status='rejected').count(),
#     }
    
#     # Pagination
#     paginator = Paginator(requests, 25)
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)
    
#     # Import necessary models
#     from app.models.human_resource import Department
#     from app.models.products import UnitOfMeasure
    
#     context = {
#         'requests': page_obj,
#         'current_status': status_filter,
#         'stores': stores,
#         'status_counts': status_counts,
#         'departments': Department.objects.filter(is_active=True),
#         'units': UnitOfMeasure.objects.all(),
#     }
    
#     return render(request, 'transfers/transfer_request_list.html', context)


# @login_required
# def transfer_request_detail(request, request_id):
#     """Display detailed view of a transfer request"""
    
#     transfer_request = get_object_or_404(
#         TransferRequest.objects.select_related(
#             'from_store', 'to_store', 'requested_by', 'approved_by'
#         ).prefetch_related('items__product'),
#         id=request_id
#     )
    
#     context = {
#         'request': transfer_request,
#     }
    
#     return render(request, 'transfers/transfer_request_details.html', context)


# # Helper view for AJAX product info
# @login_required
# @require_http_methods(["GET"])
# def get_product_info(request, product_id):
#     """Get product information for AJAX requests"""
    
#     try:
#         from app.models.products import Product
#         product = get_object_or_404(Product, id=product_id)
        
#         # Get available stock from the selected store
#         from_store_id = request.GET.get('from_store')
#         available_stock = 0
        
#         if from_store_id:
#             try:
#                 from app.models.products import Inventory
#                 inventory = Inventory.objects.get(
#                     product=product,
#                     store_id=from_store_id
#                 )
#                 available_stock = inventory.quantity_available
#             except Inventory.DoesNotExist:
#                 available_stock = 0
        
#         return JsonResponse({
#             'success': True,
#             'product': {
#                 'id': product.id,
#                 'name': product.name,
#                 'sku': product.sku,
#                 'cost_price': float(product.cost_price or 0),
#                 'selling_price': float(product.selling_price or 0),
#                 'available_stock': available_stock,
#                 'unit': product.unit or '',
#             }
#         })
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': str(e)
#         }, status=500)


# # Add validation view for transfer items
# @login_required
# @require_http_methods(["POST"])
# def validate_transfer_items(request):
#     """Validate transfer items against available stock"""
    
#     try:
#         data = json.loads(request.body)
#         from_store_id = data.get('from_store')
#         items = data.get('items', [])
        
#         if not from_store_id:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'From store is required'
#             })
        
#         validation_results = []
        
#         for item in items:
#             product_id = item.get('product')
#             quantity = item.get('quantity', 0)
            
#             if not product_id or quantity <= 0:
#                 continue
            
#             try:
#                 from app.models.products import Product
#                 from app.models.products import Inventory
                
#                 product = Product.objects.get(id=product_id)
                
#                 try:
#                     inventory = Inventory.objects.get(
#                         product=product,
#                         store_id=from_store_id
#                     )
#                     available = inventory.quantity_available
#                 except Inventory.DoesNotExist:
#                     available = 0
                
#                 validation_results.append({
#                     'product_id': product_id,
#                     'product_name': product.name,
#                     'requested_quantity': quantity,
#                     'available_quantity': available,
#                     'is_valid': quantity <= available,
#                     'shortage': max(0, quantity - available)
#                 })
                
#             except Product.DoesNotExist:
#                 validation_results.append({
#                     'product_id': product_id,
#                     'error': 'Product not found'
#                 })
        
#         return JsonResponse({
#             'success': True,
#             'validation_results': validation_results
#         })
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': str(e)
#         }, status=500)