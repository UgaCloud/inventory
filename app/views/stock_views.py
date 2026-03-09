# app/views/stock_transfer_views.py - COMPLETE FIXED VERSION
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import csv, io, json
import logging

from app.models.transactions import *
from app.forms.transaction_forms import *
from app.models.products import Product, UnitOfMeasure, Inventory, ProductUnitPrice
from app.selectors.transaction_selectors import *
from app.utils.utils import convert_to_base_units, convert_from_base_units

logger = logging.getLogger(__name__)

@login_required
def stock_transfer_list(request):
    """List all stock transfers with filtering and pagination"""
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    transfers = StockTransfer.objects.select_related(
        'from_store', 'to_store', 'created_by', 'transfer_request'
    ).prefetch_related('items').order_by('-transfer_date')
    
    # Apply filters
    if status_filter != 'all':
        transfers = transfers.filter(status=status_filter)
    
    if search_query:
        transfers = transfers.filter(
            Q(id__icontains=search_query) |
            Q(transfer_request__id__icontains=search_query) |
            Q(from_store__name__icontains=search_query) |
            Q(to_store__name__icontains=search_query) |
            Q(note__icontains=search_query)
        )
    
    # Calculate status counts for dashboard
    status_counts = {
        'pending': StockTransfer.objects.filter(status='pending').count(),
        'in_transit': StockTransfer.objects.filter(status='in_transit').count(),
        'completed': StockTransfer.objects.filter(status='completed').count(),
        'cancelled': StockTransfer.objects.filter(status='cancelled').count(),
    }
    
    # Calculate pending approved requests
    pending_approved_requests = TransferRequest.objects.filter(status='approved').count()
    
    # Calculate total value of active transfers (pending + in_transit)
    total_values = transfers.filter(status__in=['pending', 'in_transit']).aggregate(
        total_value=Sum('total_value')
    )['total_value'] or 0
    
    # Pagination
    paginator = Paginator(transfers, 25)  # Show 25 transfers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get products and units for direct transfer modal
    products = Product.objects.filter(is_active=True).order_by('name')[:100]  # Limit to 100 active products
    units = UnitOfMeasure.objects.all().order_by('name')
    
    # Create form for direct transfer
    stock_form = StockTransferForm()
    
    context = {
        'transfers': page_obj,
        'status_counts': status_counts,
        'pending_approved_requests': pending_approved_requests,
        'total_values': total_values,
        'stock_form': stock_form,
        'products': products,
        'units': units,
        'current_status': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'stock/stock_transfer_list.html', context)


@login_required
def get_product_stock_transfer_info(request):
    """JSON endpoint for real-time stock with conversion factor handling"""
    try:
        # Get parameters from GET parameters
        product_id = request.GET.get('product_id')
        store_id = request.GET.get('store_id')
        
        logger.info(f"Fetching stock for product_id: {product_id}, store_id: {store_id}")
        
        if not product_id or not store_id:
            logger.error(" Missing product_id or store_id parameters")
            return JsonResponse({
                'success': False,
                'error': 'Missing parameters',
                'available_stock': 0,
                'total_stock': 0,
                'committed_stock': 0,
                'can_fulfill': False
            }, status=400)
        
        try:
            # Convert IDs to integers
            product_id = int(product_id)
            store_id = int(store_id)
            
            # Get product info first
            product = Product.objects.get(id=product_id)
            
            # Get ALL units available for this product with conversion factors
            units_data = []
            for unit_price in product.unit_prices.all():
                units_data.append({
                    'id': unit_price.unit.id,
                    'name': unit_price.unit.name,
                    'abbreviation': unit_price.unit.abbreviation,
                    'price': float(unit_price.price),
                    'conversion_factor': float(unit_price.conversion_factor),
                    'is_base_unit': unit_price.conversion_factor == Decimal('1.0'),
                })
            
            # Get default unit (base unit should have conversion_factor = 1.0)
            default_unit = None
            default_unit_price = None
            if units_data:
                # Try to find base unit first
                base_units = [u for u in units_data if u['is_base_unit']]
                if base_units:
                    default_unit = base_units[0]
                else:
                    default_unit = units_data[0]  # Fallback to first unit
                default_unit_price = default_unit['price']
            
            # Try to get inventory for product in store
            try:
                inventory = Inventory.objects.get(
                    product_id=product_id,
                    store_id=store_id
                )
                
                total_stock = inventory.quantity_in_stock  # This should be in base units
                logger.info(f"Base inventory found: {total_stock}")
                
                # Calculate committed stock (stock reserved for pending/in-transit transfers) in BASE UNITS
                committed_stock_base = 0
                pending_items = StockTransferItem.objects.filter(
                    product_id=product_id,
                    stock_transfer__from_store_id=store_id,
                    stock_transfer__status__in=['in_transit']
                ).select_related('product', 'units')
                
                for item in pending_items:
                    # Use base_quantity field (calculated during save)
                    committed_stock_base += item.base_quantity
                
                logger.info(f"Committed stock (base units): {committed_stock_base}")
                
                # Calculate truly available stock in base units
                available_stock = max(0, total_stock - committed_stock_base)
                logger.info(f"Available stock (base units): {available_stock}")
                
                # Get unit cost - check InventoryBatch first, then product default price
                unit_cost = default_unit_price or 0
                
                # Try to get latest batch cost for this product in this store
                try:
                    latest_batch = InventoryBatch.objects.filter(
                        product=product,
                        store_id=store_id
                    ).order_by('-created_at').first()
                    
                    if latest_batch and latest_batch.unit_cost:
                        unit_cost = float(latest_batch.unit_cost)
                except Exception as e:
                    logger.warning(f"Could not get batch cost: {str(e)}")
                
                # Get unit information
                unit_name = default_unit['name'] if default_unit else 'Piece'
                unit_id = default_unit['id'] if default_unit else None
                unit_abbreviation = default_unit['abbreviation'] if default_unit else 'pc'
                reorder_level = inventory.reorder_level or 0
                
            except Inventory.DoesNotExist:
                logger.warning(f"No inventory record found for product {product_id} in store {store_id}")
                total_stock = 0
                available_stock = 0
                committed_stock_base = 0
                unit_cost = default_unit_price or 0
                unit_name = default_unit['name'] if default_unit else 'Piece'
                unit_id = default_unit['id'] if default_unit else None
                unit_abbreviation = default_unit['abbreviation'] if default_unit else 'pc'
                reorder_level = 0
            
            response_data = {
                'success': True,
                'available_stock': available_stock,  # In base units
                'total_stock': total_stock,  # In base units
                'committed_stock': committed_stock_base,  # In base units
                'reorder_level': reorder_level,
                'can_fulfill': available_stock > 0,
                'product_name': product.name,
                'sku': product.sku,
                'unit_cost': unit_cost,
                'default_price': default_unit_price or 0,
                'unit': unit_name,
                'unit_id': unit_id,
                'unit_abbreviation': unit_abbreviation,
                'units': units_data,  
            }
            
            return JsonResponse(response_data)
                
        except Product.DoesNotExist:
            logger.error(f"Product {product_id} does not exist")
            return JsonResponse({
                'success': False,
                'error': 'Product not found',
                'available_stock': 0,
                'total_stock': 0,
                'committed_stock': 0,
                'can_fulfill': False
            }, status=404)
            
    except ValueError as e:
        logger.error(f"Invalid parameter format: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid parameter format',
            'available_stock': 0,
            'total_stock': 0,
            'committed_stock': 0,
            'can_fulfill': False
        }, status=400)
            
    except Exception as e:
        logger.error(f"Error in get_product_stock_info: {str(e)}", exc_info=True)
        
        return JsonResponse({
            'success': False,
            'error': 'Unable to fetch stock information',
            'available_stock': 0,
            'total_stock': 0,
            'committed_stock': 0,
            'can_fulfill': False
        }, status=500)


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
    print(f"Transfer request found: {transfer_request}")
    
    if request.method == 'POST':
        # try:
        with transaction.atomic():
            stock_transfer = StockTransfer.objects.create(
                transfer_request=transfer_request,
                from_store=transfer_request.from_store,
                to_store=transfer_request.to_store,
                created_by=request.user,
                note=f"Created from approved request #{transfer_request.id}",
                status='pending'
            )
            print(f"Items in transfer request: {transfer_request.items.count()}")
            for request_item in transfer_request.items.all():
                # Use base_quantity from the transfer request item (already calculated)
                print(f"Creating transfer item for product {request_item.product.name} with base quantity {request_item.base_quantity}")
                StockTransferItem.objects.create(
                    stock_transfer=stock_transfer,
                    product=request_item.product,
                    quantity=request_item.base_quantity,  # Store as base quantity
                    units=request_item.units,
                    original_quantity=request_item.quantity,  # Store original for display
                    base_quantity=request_item.base_quantity,  # Explicitly store base quantity
                    transfer_request_item=request_item
                )
            
            transfer_request.status = 'fulfilled'
            transfer_request.save()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': True, 'transfer_id': stock_transfer.id}, status=201)

            messages.success(request, f'Stock transfer #{stock_transfer.id} created successfully from request #{transfer_request.id}.')
            return redirect('stock_transfer_detail', transfer_id=stock_transfer.id)
                
        # except Exception as e:
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
                        # Use base_quantity from the transfer request item
                        StockTransferItem.objects.create(
                            stock_transfer=stock_transfer,
                            product=request_item.product,
                            quantity=request_item.base_quantity,  # Store as base quantity
                            units=request_item.units,
                            original_quantity=request_item.quantity,  # Store original for display
                            base_quantity=request_item.base_quantity,  # Explicitly store base quantity
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
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'success': True, 'created': created_count, 'errors': errors}, status=200)

        return redirect('stock_transfer_list')
    
    return redirect('stock_transfer_list')

@login_required
def direct_stock_transfer_create(request):
    """Create a direct stock transfer with conversion factor handling"""
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
                            quantity = Decimal(quantity)
                            
                            # Get conversion factor for this product-unit combination
                            try:
                                product_unit = ProductUnitPrice.objects.get(
                                    product=product,
                                    unit=unit
                                )
                                conversion_factor = Decimal(product_unit.conversion_factor)
                            except ProductUnitPrice.DoesNotExist:
                                # No conversion factor defined, assume it's base unit
                                conversion_factor = Decimal(1.0)
                                messages.warning(
                                    request, 
                                    f"No conversion factor defined for {product.name} with unit {unit.name}. Using 1.0 as default."
                                )
                            
                            # Calculate quantity in base units
                            base_quantity = int(quantity * conversion_factor)
                            
                            if base_quantity > 0:
                                # Check stock availability in base units
                                try:
                                    inventory = Inventory.objects.get(
                                        product=product,
                                        store=from_store
                                    )
                                    if inventory.quantity_in_stock < base_quantity:
                                        messages.error(
                                            request, 
                                            f"Insufficient stock for {product.name}. "
                                            f"Available: {inventory.quantity_in_stock} base units, "
                                            f"Required: {base_quantity} base units ({quantity} {unit.name})"
                                        )
                                        continue
                                except Inventory.DoesNotExist:
                                    messages.error(
                                        request, 
                                        f"No inventory found for {product.name} in {from_store.name}"
                                    )
                                    continue
                                
                                # Create transfer item with base quantity
                                StockTransferItem.objects.create(
                                    stock_transfer=transfer,
                                    product=product,
                                    quantity=base_quantity,  # Store in base units
                                    units=unit,
                                    original_quantity=int(quantity),  # Store original for display
                                    base_quantity=base_quantity  # Explicitly store base quantity
                                )
                                items_created += 1
                                
                        except (Product.DoesNotExist, UnitOfMeasure.DoesNotExist, ValueError) as e:
                            logger.error(f"Error processing item {i}: {str(e)}")
                            continue
                
                if items_created > 0:
                    messages.success(request, f'Transfer #{transfer.id} created successfully with {items_created} items!')
                    return redirect('stock_transfer_detail', transfer_id=transfer.id)
                else:
                    transfer.delete()
                    messages.error(request, 'No valid items were added. Transfer cancelled.')
                    return redirect('stock_transfer_list')
                    
        except Exception as e:
            logger.error(f"Error creating direct transfer: {str(e)}", exc_info=True)
            messages.error(request, f'Error creating transfer: {str(e)}')
    
    return redirect('stock_transfer_list')

@login_required
def start_stock_transfer(request, transfer_id):
    """Mark a transfer as in transit with base unit validation - handles both regular and AJAX requests"""
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    
    if transfer.status != 'pending':
        message = 'Only pending transfers can be started.'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': message})
        messages.error(request, message)
        return redirect('stock_transfer_detail', transfer_id=transfer.id)
    
    stock_issues = []
    for item in transfer.items.all():
        try:
            inventory = Inventory.objects.get(
                product=item.product, 
                store=transfer.from_store
            )
            # Check using base_quantity (already calculated)
            if inventory.quantity_in_stock < item.base_quantity:
                stock_issues.append(
                    f"{item.product.name}: Available {inventory.quantity_in_stock} base units, "
                    f"Required {item.base_quantity} base units "
                    f"({item.original_quantity} {item.units.name if item.units else 'units'})"
                )
        except Inventory.DoesNotExist:
            stock_issues.append(f"{item.product.name}: No inventory found")
    
    if stock_issues:
        message = f'Insufficient stock: {", ".join(stock_issues)}'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': message})
        messages.error(request, message)
        return redirect('stock_transfer_detail', transfer_id=transfer.id)
    
    transfer.status = 'in_transit'
    transfer.save()
    
    message = f'Stock transfer #{transfer.id} marked as in transit.'
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': message})
    
    messages.success(request, message)
    return redirect('stock_transfer_detail', transfer_id=transfer.id)


@login_required
def complete_stock_transfer(request, transfer_id):
    """Complete stock transfer"""
    try:
        with transaction.atomic():
            transfer = StockTransfer.objects.select_for_update().get(id=transfer_id)
            
            if transfer.status != 'in_transit':
                messages.error(request, 'Only transfers in transit can be completed.')
                return redirect('stock_transfer_detail', transfer_id=transfer.id)
            
            if transfer.status == 'completed':
                messages.info(request, f'Transfer #{transfer.id} is already completed.')
                return redirect('stock_transfer_detail', transfer_id=transfer.id)
            
            # Apply inventory changes
            if not transfer.inventory_changes_applied:
                transfer.apply_inventory_changes()
            
            # Update status
            transfer.status = 'completed'
            transfer.completed_by = str(request.user) if request.user else None
            transfer.inventory_changes_applied = True
            
            # Save WITHOUT triggering the old auto-logic
            super(StockTransfer, transfer).save(update_fields=[
                'status', 
                'completed_by', 
                'inventory_changes_applied'
            ])
            
            messages.success(request, f'Stock transfer #{transfer.id} completed successfully.')
            
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('stock_transfer_detail', transfer_id=transfer_id)

@login_required
def transfer_request_list(request):
    """List all transfer requests"""
    requests = TransferRequest.objects.all().order_by('-request_date')
    return render(request, 'stock/transfer_request_list.html', {'transfer_requests': requests})

@login_required
def create_transfer_request(request):
    """Create a new transfer request with conversion factor handling"""
    if request.method == 'POST':
        form = TransferRequestForm(request.POST)
        formset = TransferRequestItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            transfer_request = form.save(commit=False)
            transfer_request.requested_by = request.user
            transfer_request.save()
            
            formset.instance = transfer_request
            formset.save()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': True, 'request_id': transfer_request.id})

            messages.success(request, 'Transfer request created successfully.')
            return redirect('transfer_request_detail', request_id=transfer_request.id)
        else:
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
            'quantity': it.quantity,  # Display quantity
            'base_quantity': it.base_quantity,  # Base units (calculated)
            'units_id': it.units.id,
            'units_name': it.units.name,
            'units_abbreviation': it.units.abbreviation,
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
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': True, 'request_id': transfer_request.id})

            messages.success(request, 'Transfer request updated successfully.')
            return redirect('transfer_request_detail', request_id=transfer_request.id)
        else:
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
    """Update transfer request"""
    transfer_request = get_object_or_404(TransferRequest, id=request_id)
    
    if request.method == 'POST':
        form = TransferRequestForm(request.POST, instance=transfer_request)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transfer request updated successfully.')
            return redirect('transfer_request_detail', request_id=transfer_request.id)
    
    return redirect('transfer_request_detail', request_id=request_id)

@login_required
def pending_transfer_requests_for_approval(request):
    """Show pending transfer requests for approval"""
    pending_requests = TransferRequest.objects.filter(status='pending').order_by('-request_date')
    return render(request, 'stock/pending_transfer_requests.html', {'pending_requests': pending_requests})

# Purchase Order Functions
@login_required
def purchase_order_list(request):
    """List purchase orders"""
    orders = get_all_orders()
    form = PurchaseOrderForm()
    
    # Add these lines to get suppliers and stores
    from app.models.suppliers import Supplier
    from app.models.products import StoreLocation
    
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    stores = StoreLocation.objects.filter(is_active=True).order_by('name')
    
    context = {
        'purchase_orders': orders,
        'form': form,
        'suppliers': suppliers,  # Add this
        'stores': stores,        # Add this
    }
    return render(request, 'stock/purchase_order_list.html', context)

@login_required
def purchase_order_detail(request, order_id):
    """View purchase order details"""
    order = get_order_by_id(order_id)
    return render(request, 'purchase_order_detail.html', {'order': order})

@login_required
def create_purchase_order(request):
    """Create a new purchase order with formset"""
    # Get all necessary data for dropdowns
    from app.models.suppliers import Supplier
    from app.models.products import StoreLocation
    from app.models.organization import Branch
    
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    stores = StoreLocation.objects.filter(is_active=True).order_by('name')
    branches = Branch.objects.filter(is_active=True).order_by('name')
    products = Product.objects.filter(is_active=True).order_by('name')[:100]
    
    PurchaseOrderItemFormSet = inlineformset_factory(
        PurchaseOrder,
        PurchaseOrderItem,
        form=PurchaseOrderItemForm,
        extra=1,
        can_delete=True,
        fields='__all__'
    )
    
    if request.method == 'POST':
        # Create a mutable copy of POST data
        post_data = request.POST.copy()
        
        # Set default status to PENDING
        post_data['status'] = 'PENDING'
        post_data['total_cost'] = '0.00'
        
        form = PurchaseOrderForm(post_data)
        formset = PurchaseOrderItemFormSet(post_data)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Save purchase order
                    order = form.save(commit=False)
                    order.recorded_by = request.user.username
                    order.status = 'PENDING'  # Explicitly set to PENDING
                    order.total_cost = 0.00
                    order.save()
                    
                    # Calculate total from items
                    total_cost = 0
                    
                    # Save formset items
                    instances = formset.save(commit=False)
                    for instance in instances:
                        instance.order = order
                        instance.save()
                        total_cost += instance.quantity * instance.unit_cost
                    
                    # Update order total cost
                    order.total_cost = total_cost
                    order.save(update_fields=['total_cost'])
                    
                    # Delete any marked items
                    for obj in formset.deleted_objects:
                        obj.delete()
                    
                    messages.success(request, f'Purchase order #{order.id} created successfully.')
                    return redirect('purchase_order_item_list', order_id=order.id)
                    
            except Exception as e:
                messages.error(request, f'Error creating purchase order: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PurchaseOrderForm()
        formset = PurchaseOrderItemFormSet()
    
    # Get all purchase orders for the table
    purchase_orders = PurchaseOrder.objects.all().order_by('-purchase_date')
    
    return render(request, 'stock/purchase_order_list.html', {
        'form': form,
        'items_formset': formset,
        'purchase_orders': purchase_orders,
        'suppliers': suppliers,
        'stores': stores,
        'branches': branches,
        'products': products,
    })



@login_required
def get_purchase_order_api(request, order_id):
    """API endpoint to get purchase order data for editing"""
    try:
        # Get the purchase order
        order = PurchaseOrder.objects.get(pk=order_id)
        
        # Get items with related product and unit
        items = PurchaseOrderItem.objects.filter(order=order).select_related('product', 'unit')
        
        # Prepare order data - matching your actual model fields (NO BRANCH)
        order_data = {
            'id': order.id,
            'supplier_id': order.supplier_id,
            'store_id': order.store_id,
            'purchase_date': order.purchase_date.strftime('%Y-%m-%d') if order.purchase_date else None,
            'expected_date': order.expected_date.strftime('%Y-%m-%d') if order.expected_date else None,
            'status': order.status,
            'recorded_by': order.recorded_by,
            'note': order.note,
            'total_cost': float(order.total_cost) if order.total_cost else 0,
        }
        
        # Prepare items data
        items_data = []
        for item in items:
            # Get product unit information for this product
            product_units = []
            if item.product:
                try:
                    # Get all units available for this product through unit_prices
                    for unit_price in item.product.unit_prices.select_related('unit').all():
                        product_units.append({
                            'unit_id': unit_price.unit.id,
                            'unit_name': unit_price.unit.name,
                            'abbreviation': unit_price.unit.abbreviation,
                            'conversion_factor': float(unit_price.conversion_factor) if unit_price.conversion_factor else 1,
                            'is_base_unit': unit_price.conversion_factor == 1,
                            'price': float(unit_price.price) if unit_price.price else 0,
                        })
                except Exception as e:
                    logger.error(f"Error getting product units for item {item.id}: {e}")
            
            items_data.append({
                'id': item.id,
                'product_id': item.product_id,
                'product_name': item.product.name if item.product else '',
                'product_sku': item.product.sku if item.product else '',
                'unit_id': item.unit_id,
                'unit_name': item.unit.name if item.unit else '',
                'unit_abbreviation': item.unit.abbreviation if item.unit else '',
                'quantity': float(item.quantity) if item.quantity else 0,
                'base_quantity': float(item.base_quantity) if item.base_quantity else 0,
                'unit_cost': float(item.unit_cost) if item.unit_cost else 0,
                'expiry_date': item.expiry_date.strftime('%Y-%m-%d') if item.expiry_date else None,
                'product_units': product_units,
            })
        
        response_data = {
            'success': True,
            'order': order_data,
            'items': items_data
        }
        
        logger.info(f"Successfully fetched purchase order {order_id} with {len(items_data)} items")
        return JsonResponse(response_data)
        
    except PurchaseOrder.DoesNotExist:
        logger.error(f"Purchase order {order_id} not found")
        return JsonResponse({
            'success': False, 
            'error': f'Purchase order {order_id} not found'
        }, status=404)
        
    except Exception as e:
        logger.error(f"Error fetching purchase order {order_id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@login_required
def edit_purchase_order(request, order_id):
    """Edit an existing purchase order"""
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    
    # Get all necessary data for dropdowns
    from app.models.suppliers import Supplier
    from app.models.products import StoreLocation
    from app.models.organization import Branch
    
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    stores = StoreLocation.objects.filter(is_active=True).order_by('name')
    branches = Branch.objects.filter(is_active=True).order_by('name')
    products = Product.objects.filter(is_active=True).order_by('name')[:100]
    
    PurchaseOrderItemFormSet = inlineformset_factory(
        PurchaseOrder,
        PurchaseOrderItem,
        form=PurchaseOrderItemForm,
        extra=0,
        can_delete=True,
        fields='__all__'
    )
    
    if request.method == 'POST':
        # print("=" * 50)
        # print("EDIT POST DATA:")
        # print(request.POST)
        # print("=" * 50)
        
        form = PurchaseOrderForm(request.POST, instance=order)
        formset = PurchaseOrderItemFormSet(request.POST, instance=order)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Save purchase order
                    order = form.save(commit=False)
                    order.save()  # Save without update_fields
                    
                    # Calculate total from items
                    total_cost = 0
                    
                    # Save formset items
                    instances = formset.save(commit=False)
                    for instance in instances:
                        instance.order = order
                        instance.save()
                        total_cost += instance.quantity * instance.unit_cost
                    
                    # Handle deleted items
                    for obj in formset.deleted_objects:
                        obj.delete()
                    
                    # Update order total cost and save the entire model
                    order.total_cost = total_cost
                    order.save()  # Save without update_fields
                    
                    messages.success(request, f'Purchase order #{order.id} updated successfully.')
                    return redirect('purchase_order_item_list', order_id=order.id)
                    
            except Exception as e:
                messages.error(request, f'Error updating purchase order: {str(e)}')
                import traceback
                traceback.print_exc()
        else:
            # Collect error messages
            error_messages = []
            for field, errors in form.errors.items():
                error_messages.append(f"{field}: {', '.join(errors)}")
            
            for i, form_errors in enumerate(formset.errors):
                if form_errors:
                    for field, errors in form_errors.items():
                        if field == '__all__':
                            error_messages.append(f"Item {i+1}: {', '.join(errors)}")
                        else:
                            error_messages.append(f"Item {i+1} - {field}: {', '.join(errors)}")
            
            messages.error(request, 'Please correct the errors below: ' + ' | '.join(error_messages))
            
            return render(request, 'stock/purchase_order_list.html', {
                'form': form,
                'items_formset': formset,
                'purchase_orders': PurchaseOrder.objects.all().order_by('-purchase_date'),
                'suppliers': suppliers,
                'stores': stores,
                'branches': branches,
                'products': products,
                'editing_order': order,
            })
    else:
        form = PurchaseOrderForm(instance=order)
        formset = PurchaseOrderItemFormSet(instance=order)
    
    # Get all purchase orders for the table
    purchase_orders = PurchaseOrder.objects.all().order_by('-purchase_date')
    
    return render(request, 'stock/purchase_order_list.html', {
        'form': form,
        'items_formset': formset,
        'purchase_orders': purchase_orders,
        'suppliers': suppliers,
        'stores': stores,
        'branches': branches,
        'products': products,
        'editing_order': order
    })



@login_required
def delete_purchase_order(request, order_id):
    """Delete a purchase order"""
    order = get_object_or_404(PurchaseOrder, id=order_id)
    if request.method == 'POST':
        order.delete()
        messages.success(request, 'Purchase order deleted successfully.')
        return redirect('purchase_order_list')
    return render(request, 'purchase_order_confirm_delete.html', {'order': order})

@login_required
def purchase_order_item_list(request, order_id):
    """List items for a purchase order"""
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
    """Create a purchase order item with conversion factor handling"""
    order = get_object_or_404(PurchaseOrder, id=order_id)
    if request.method == 'POST':
        form = PurchaseOrderItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.order = order
            
            # Handle conversion factor if needed (purchase orders might need it too)
            try:
                # Get conversion factor for this product-unit combination
                product_unit = ProductUnitPrice.objects.get(
                    product=item.product,
                    unit=item.unit
                )
                # Note: PurchaseOrderItem doesn't have base_quantity field yet
                # You might want to add it similar to TransferRequestItem
            except ProductUnitPrice.DoesNotExist:
                # No conversion factor defined
                pass
            
            item.save()
            messages.success(request, 'Purchase order item added successfully.')
        return redirect('purchase_order_item_list', order_id=order.id)
    else:
        form = PurchaseOrderItemForm()
    return render(request, 'stock/purchase_order_item_form.html', {'form': form, 'order': order})

@login_required
def edit_purchase_order_item(request, item_id):
    """Edit a purchase order item"""
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
    """Delete a purchase order item"""
    item = get_object_or_404(PurchaseOrderItem, id=item_id)
    order = item.order
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Purchase order item deleted successfully.')
        return redirect('purchase_order_item_list', order_id=order.id)
    return render(request, 'purchase_order_item_confirm_delete.html', {'item': item, 'order': order})

# Stock Adjustment Functions
@login_required
def stock_adjustment_list(request):
    """List stock adjustments"""
    adjustments = StockAdjustment.objects.all().order_by('-created_at')
    form = StockAdjustmentForm()
    context = {
        'adjustments': adjustments,
        'form': form,
    }
    return render(request, 'stock/stock_adjustment_list.html', context)

@login_required
def stock_adjustment_detail(request, adjustment_id):
    """View stock adjustment details"""
    adjustment = get_object_or_404(
        StockAdjustment.objects.select_related('product', 'store', 'unit', 'created_by'),
        id=adjustment_id
    )
    adjustment.refresh_from_db()
    
    related_adjustments = []
    batch_totals = {}
    if adjustment.reference:
        related_adjustments = StockAdjustment.objects.filter(
            reference=adjustment.reference,
            store=adjustment.store
        ).select_related('product', 'unit').order_by('created_at')
        
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
    
    stock_movements = StockMovement.objects.filter(
        transaction_type='ADJUSTMENT',
        transaction_id=adjustment.id
    ).select_related('product', 'store').order_by('-timestamp')
    
    from app.models.products import Inventory
    try:
        current_inventory = Inventory.objects.get(
            product=adjustment.product,
            store=adjustment.store
        )
        current_inventory.refresh_from_db()
        current_quantity = current_inventory.quantity_in_stock
    except Inventory.DoesNotExist:
        current_quantity = 0
    
    record_was_edited = False
    actual_quantity_change = None
    
    if adjustment.status == 'applied' and stock_movements.exists():
        movement = stock_movements.first()
        actual_quantity_change = movement.quantity
        quantity_after_actual = movement.units_in_stock
        quantity_before = quantity_after_actual - actual_quantity_change
        if quantity_before < 0:
            quantity_before = 0
        quantity_after = quantity_after_actual
        record_was_edited = (actual_quantity_change != adjustment.quantity_change)
    elif adjustment.status == 'pending':
        quantity_before = current_quantity
        quantity_after = max(0, current_quantity + adjustment.quantity_change)
    else:
        quantity_before = None
        quantity_after = current_quantity
    
    total_value = None
    qty_for_value = actual_quantity_change if actual_quantity_change is not None else adjustment.quantity_change
    if adjustment.unit_cost and qty_for_value:
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
    """Create a stock adjustment"""
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            adj = form.save(commit=False)
            
            # Correctly assign the user object
            adj.created_by = request.user

            adj.status = 'pending' 
            adj.save()
            messages.success(request, 'Stock adjustment created successfully.')
            return redirect('stock_adjustment_list')
        else:
            messages.error(request, f'Form errors: {form.errors}')
    else:
        form = StockAdjustmentForm()
    
    return render(request, 'stock/stock_adjustment_form.html', {'form': form})


@login_required
def edit_stock_adjustment(request, adjustment_id):
    """Edit a stock adjustment"""
    adjustment = get_object_or_404(StockAdjustment, id=adjustment_id)
    
    if adjustment.status == 'applied':
        messages.warning(request, 'Cannot edit applied adjustments.')
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
    """Apply a stock adjustment"""
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
    """Delete a stock adjustment"""
    adjustment = get_object_or_404(StockAdjustment, id=adjustment_id)
    if request.method == 'POST':
        adjustment.delete()
        messages.success(request, 'Stock adjustment deleted successfully.')
        return redirect('stock_adjustment_list')
    return render(request, 'stock/stock_adjustment_confirm_delete.html', {'adjustment': adjustment})