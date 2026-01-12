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
from decimal import Decimal
import logging

from app.models.transactions import *
from app.models.human_resource import *
from app.models.products import *
from app.forms.transaction_forms import *
from app.selectors.transfer_selectors import *
from app.selectors.product_selectors import get_stores

logger = logging.getLogger(__name__)

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
        'fulfilled': requests.filter(status='fulfilled').count(),
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
    """Handle transfer request creation via AJAX with conversion factor support"""
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
            
            from_store = StoreLocation.objects.get(pk=data['from_store'])
            errors = []
            
            # Check stock availability for each item WITH CONVERSION FACTORS
            for i, item in enumerate(data['items']):
                try:
                    product = Product.objects.get(pk=item['product_id'])
                    unit = UnitOfMeasure.objects.get(pk=item['units_id'])
                    
                    # Get conversion factor for this product-unit combination
                    try:
                        product_unit = ProductUnitPrice.objects.get(
                            product=product,
                            unit=unit
                        )
                        conversion_factor = Decimal(str(product_unit.conversion_factor))
                    except ProductUnitPrice.DoesNotExist:
                        conversion_factor = Decimal('1.0')
                        logger.warning(f"No conversion factor found for product {product.id} with unit {unit.id}, using 1.0")
                    
                    # Calculate quantity in base units
                    display_quantity = Decimal(str(item['quantity']))
                    base_quantity_needed = int(display_quantity * conversion_factor)
                    
                    # Get available stock in base units
                    try:
                        inventory = Inventory.objects.get(product=product, store=from_store)
                        physical_stock = inventory.quantity_in_stock  # Already in base units
                    except Inventory.DoesNotExist:
                        physical_stock = 0
                    
                    # Calculate committed stock in base units
                    committed_stock_base = 0
                    committed_items = StockTransferItem.objects.filter(
                        product=product,
                        stock_transfer__from_store=from_store,
                        stock_transfer__status__in=['pending', 'in_transit']
                    ).select_related('units')
                    
                    for committed_item in committed_items:
                        committed_stock_base += committed_item.base_quantity
                    
                    available_stock = max(0, physical_stock - committed_stock_base)
                    
                    # Validate against base quantity needed
                    if base_quantity_needed > available_stock:
                        # Calculate max display units possible
                        max_display_units = int(available_stock / conversion_factor) if conversion_factor > 0 else 0
                        remaining_base_units = available_stock % conversion_factor
                        
                        error_msg = (
                            f"Item {i+1} ({product.name}): "
                            f"Requested {display_quantity} {unit.name} "
                            f"(= {base_quantity_needed} base units) "
                            f"exceeds available stock ({available_stock} base units). "
                            f"Maximum: {max_display_units} {unit.name}"
                        )
                        
                        if remaining_base_units > 0:
                            error_msg += f" + {remaining_base_units} base units"
                        
                        errors.append(error_msg)
                        
                except (Product.DoesNotExist, UnitOfMeasure.DoesNotExist) as e:
                    errors.append(f"Item {i+1}: {str(e)}")
                except Exception as e:
                    errors.append(f"Item {i+1}: Error - {str(e)}")
            
            if errors:
                return JsonResponse({
                    'success': False,
                    'error': 'Stock validation failed',
                    'details': errors
                }, status=400)
            
            # Create transfer request with conversion factors
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
                
                # Create items with base quantity calculation
                for item in data['items']:
                    product = Product.objects.get(pk=item['product_id'])
                    unit = UnitOfMeasure.objects.get(pk=item['units_id'])
                    
                    # Get conversion factor
                    try:
                        product_unit = ProductUnitPrice.objects.get(
                            product=product,
                            unit=unit
                        )
                        conversion_factor = Decimal(str(product_unit.conversion_factor))
                    except ProductUnitPrice.DoesNotExist:
                        conversion_factor = Decimal('1.0')
                    
                    display_quantity = Decimal(str(item['quantity']))
                    base_quantity = int(display_quantity * conversion_factor)
                    
                    TransferRequestItem.objects.create(
                        transfer_request=transfer_request,
                        product=product,
                        quantity=int(display_quantity),  # Store display quantity
                        units=unit,
                        base_quantity=base_quantity,  # Store calculated base quantity
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
            logger.error(f"Error creating transfer request: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@login_required
@csrf_exempt
def update_transfer_request(request, request_id):
    """Update transfer request via AJAX with conversion factor support"""
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
            
            from_store = StoreLocation.objects.get(pk=data['from_store'])
            errors = []
            
            # Check stock availability for each item WITH CONVERSION FACTORS
            for i, item in enumerate(data['items']):
                try:
                    product = Product.objects.get(pk=item['product_id'])
                    unit = UnitOfMeasure.objects.get(pk=item['units_id'])
                    
                    # Get conversion factor
                    try:
                        product_unit = ProductUnitPrice.objects.get(
                            product=product,
                            unit=unit
                        )
                        conversion_factor = Decimal(str(product_unit.conversion_factor))
                    except ProductUnitPrice.DoesNotExist:
                        conversion_factor = Decimal('1.0')
                    
                    # Calculate base quantity needed
                    display_quantity = Decimal(str(item['quantity']))
                    base_quantity_needed = int(display_quantity * conversion_factor)
                    
                    # Get available stock in base units
                    try:
                        inventory = Inventory.objects.get(product=product, store=from_store)
                        physical_stock = inventory.quantity_in_stock
                    except Inventory.DoesNotExist:
                        physical_stock = 0
                    
                    # Calculate committed stock excluding this request's items
                    committed_stock_base = 0
                    committed_items = StockTransferItem.objects.filter(
                        product=product,
                        stock_transfer__from_store=from_store,
                        stock_transfer__status__in=['pending', 'in_transit']
                    ).exclude(
                        stock_transfer__transfer_request=transfer_request
                    ).select_related('units')
                    
                    for committed_item in committed_items:
                        committed_stock_base += committed_item.base_quantity
                    
                    available_stock = max(0, physical_stock - committed_stock_base)
                    
                    # Validate against base quantity needed
                    if base_quantity_needed > available_stock:
                        # Calculate max display units possible
                        max_display_units = int(available_stock / conversion_factor) if conversion_factor > 0 else 0
                        remaining_base_units = available_stock % conversion_factor
                        
                        error_msg = (
                            f"Item {i+1} ({product.name}): "
                            f"Requested {display_quantity} {unit.name} "
                            f"(= {base_quantity_needed} base units) "
                            f"exceeds available stock ({available_stock} base units). "
                            f"Maximum: {max_display_units} {unit.name}"
                        )
                        
                        if remaining_base_units > 0:
                            error_msg += f" + {remaining_base_units} base units"
                        
                        errors.append(error_msg)
                        
                except (Product.DoesNotExist, UnitOfMeasure.DoesNotExist) as e:
                    errors.append(f"Item {i+1}: {str(e)}")
                except Exception as e:
                    errors.append(f"Item {i+1}: Error - {str(e)}")
            
            if errors:
                return JsonResponse({
                    'success': False,
                    'error': 'Stock validation failed',
                    'details': errors
                }, status=400)
            
            # Update transfer request with conversion factors
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
                
                # Create new items with base quantity calculation
                for item in data['items']:
                    product = Product.objects.get(pk=item['product_id'])
                    unit = UnitOfMeasure.objects.get(pk=item['units_id'])
                    
                    # Get conversion factor
                    try:
                        product_unit = ProductUnitPrice.objects.get(
                            product=product,
                            unit=unit
                        )
                        conversion_factor = Decimal(str(product_unit.conversion_factor))
                    except ProductUnitPrice.DoesNotExist:
                        conversion_factor = Decimal('1.0')
                    
                    display_quantity = Decimal(str(item['quantity']))
                    base_quantity = int(display_quantity * conversion_factor)
                    
                    TransferRequestItem.objects.create(
                        transfer_request=transfer_request,
                        product=product,
                        quantity=int(display_quantity),
                        units=unit,
                        base_quantity=base_quantity,
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
            logger.error(f"Error updating transfer request: {str(e)}", exc_info=True)
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
    """Get units available for a specific product with conversion factors"""
    try:
        product = Product.objects.get(pk=product_id)
        units = product.unit_prices.all().select_related('unit')
        
        units_data = [
            {
                'id': unit.unit.id,
                'name': unit.unit.name,
                'abbreviation': unit.unit.abbreviation,
                'conversion_factor': float(unit.conversion_factor),
                'price': float(unit.price),
                'is_base_unit': unit.conversion_factor == Decimal('1.0')
            }
            for unit in units
        ]
        
        # Sort: base unit first, then by conversion factor
        units_data.sort(key=lambda x: (not x['is_base_unit'], x['conversion_factor']))
        
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
        logger.error(f"Error getting product units: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def get_product_stock_for_store(request, product_id, store_id):
    """Get real-time stock for a product in a specific store with conversion factor context"""
    try:
        product = Product.objects.get(pk=product_id)
        store = StoreLocation.objects.get(pk=store_id)
        
        # Get inventory
        try:
            inventory = Inventory.objects.get(product=product, store=store)
            physical_stock = inventory.quantity_in_stock  # Base units
        except Inventory.DoesNotExist:
            physical_stock = 0
        
        # Calculate committed stock in BASE UNITS
        committed_stock_base = 0
        committed_items = StockTransferItem.objects.filter(
            product=product,
            stock_transfer__from_store=store,
            stock_transfer__status__in=['pending', 'in_transit']
        ).select_related('units')
        
        for item in committed_items:
            committed_stock_base += item.base_quantity
        
        available_stock = max(0, physical_stock - committed_stock_base)
        
        return JsonResponse({
            'success': True,
            'stock': {
                'physical_stock': physical_stock,  # Base units
                'committed_stock': committed_stock_base,  # Base units
                'available_stock': available_stock,  # Base units
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
        logger.error(f"Error getting product stock: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def get_product_unit_price(request, product_id, unit_id):
    """Get price and conversion factor for a specific product unit"""
    try:
        unit_price = ProductUnitPrice.objects.get(product_id=product_id, unit_id=unit_id)
        
        return JsonResponse({
            'success': True,
            'unit_price': {
                'id': unit_price.id,
                'product_id': unit_price.product_id,
                'unit_id': unit_price.unit_id,
                'unit_name': unit_price.unit.name,
                'unit_abbreviation': unit_price.unit.abbreviation,
                'price': float(unit_price.price),
                'conversion_factor': float(unit_price.conversion_factor),
                'is_base_unit': unit_price.conversion_factor == Decimal('1.0')
            }
        })
    except ProductUnitPrice.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unit price not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting product unit price: {str(e)}", exc_info=True)
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
            # Get conversion factor for this item
            try:
                product_unit = ProductUnitPrice.objects.get(
                    product=item.product,
                    unit=item.units
                )
                conversion_factor = float(product_unit.conversion_factor)
            except ProductUnitPrice.DoesNotExist:
                conversion_factor = 1.0
            
            items_data.append({
                'id': item.id,
                'product_id': item.product_id,
                'product_name': item.product.name,
                'product_sku': item.product.sku,
                'quantity': item.quantity,  # Display quantity
                'base_quantity': item.base_quantity,  # Base units
                'units_id': item.units_id,
                'units_name': item.units.name if item.units else None,
                'units_abbreviation': item.units.abbreviation if item.units else '',
                'conversion_factor': conversion_factor,
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
                'reason': transfer_request.note,
                'status': transfer_request.status,
                'items': items_data
            }
        })
    except TransferRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transfer request not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting transfer request JSON: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def stock_transfer_list(request):
    # Delegate to the canonical stock_transfer_list implementation in app.views.transfers
    from app.views.stock_views import stock_transfer_list as canonical_stock_transfer_list
    return canonical_stock_transfer_list(request)

@login_required
def stock_transfer_create(request):
    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        formset = StockTransferItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            transfer = form.save(commit=False)
            transfer.created_by = request.user
            transfer.save()
            
            # Process items with conversion factors
            for form_item in formset:
                if form_item.is_valid() and form_item.cleaned_data:
                    item = form_item.save(commit=False)
                    item.stock_transfer = transfer
                    
                    # Calculate base quantity if units are selected
                    if item.units and item.quantity:
                        try:
                            product_unit = ProductUnitPrice.objects.get(
                                product=item.product,
                                unit=item.units
                            )
                            conversion_factor = product_unit.conversion_factor
                            item.base_quantity = int(item.quantity * conversion_factor)
                            item.original_quantity = item.quantity
                        except ProductUnitPrice.DoesNotExist:
                            item.base_quantity = item.quantity
                            item.original_quantity = item.quantity
                    
                    item.save()
           
            messages.success(request, 'Stock transfer created successfully.')
            
        return redirect(stock_transfer_list)
    
    else:
        form = StockTransferForm()
        formset = StockTransferItemFormSet()
    
    return render(request, 'transfers/stock_transfer_form.html', {
        'form': form,
        'formset': formset
    })

@login_required
def stock_transfer_detail(request, pk):
    transfer_obj = get_stock_transfer_by_id(pk)
    if not transfer_obj:
        return render(request, '404.html', status=404)
    
    # Add conversion factor info to items
    items_with_cf = []
    for item in transfer_obj.items.all():
        try:
            product_unit = ProductUnitPrice.objects.get(
                product=item.product,
                unit=item.units
            )
            conversion_factor = product_unit.conversion_factor
            display_quantity = item.original_quantity or item.quantity
        except (ProductUnitPrice.DoesNotExist, AttributeError):
            conversion_factor = 1.0
            display_quantity = item.quantity
        
        items_with_cf.append({
            'item': item,
            'conversion_factor': conversion_factor,
            'display_quantity': display_quantity,
            'base_quantity': item.base_quantity or item.quantity
        })
    
    return render(request, 'transfers/stock_transfer_detail.html', {
        'transfer_obj': transfer_obj,
        'items_with_cf': items_with_cf
    })

@login_required
def stock_transfer_update(request, pk):
    transfer = get_object_or_404(StockTransfer, pk=pk)
    
    if request.method == 'POST':
        form = StockTransferForm(request.POST, instance=transfer)
        formset = StockTransferItemFormSet(request.POST, instance=transfer)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            
            # Update items with conversion factors
            for form_item in formset:
                if form_item.is_valid() and form_item.cleaned_data:
                    item = form_item.save(commit=False)
                    
                    # Calculate base quantity if units are selected
                    if item.units and item.quantity:
                        try:
                            product_unit = ProductUnitPrice.objects.get(
                                product=item.product,
                                unit=item.units
                            )
                            conversion_factor = product_unit.conversion_factor
                            item.base_quantity = int(item.quantity * conversion_factor)
                            item.original_quantity = item.quantity
                        except ProductUnitPrice.DoesNotExist:
                            item.base_quantity = item.quantity
                            item.original_quantity = item.quantity
                    
                    item.save()
            
            messages.success(request, 'Stock transfer updated successfully.')
            return redirect('stock_transfer_list')
    else:
        form = StockTransferForm(instance=transfer)
        formset = StockTransferItemFormSet(instance=transfer)
    
    return render(request, 'stock_transfer_form.html', {
        'form': form, 
        'item_formset': formset,
        'transfer': transfer
    })

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
        
        # Validate stock availability before approval
        errors = []
        for item in transfer_request.items.all():
            try:
                # Get conversion factor for this item
                try:
                    product_unit = ProductUnitPrice.objects.get(
                        product=item.product,
                        unit=item.units
                    )
                    conversion_factor = product_unit.conversion_factor
                except ProductUnitPrice.DoesNotExist:
                    conversion_factor = Decimal('1.0')
                
                # Calculate base quantity needed
                base_quantity_needed = item.base_quantity
                
                # Get available stock
                try:
                    inventory = Inventory.objects.get(
                        product=item.product,
                        store=transfer_request.from_store
                    )
                    physical_stock = inventory.quantity_in_stock
                except Inventory.DoesNotExist:
                    physical_stock = 0
                
                # Calculate committed stock
                committed_stock_base = 0
                committed_items = StockTransferItem.objects.filter(
                    product=item.product,
                    stock_transfer__from_store=transfer_request.from_store,
                    stock_transfer__status__in=['pending', 'in_transit']
                ).exclude(
                    stock_transfer__transfer_request=transfer_request
                ).select_related('units')
                
                for committed_item in committed_items:
                    committed_stock_base += committed_item.base_quantity
                
                available_stock = max(0, physical_stock - committed_stock_base)
                
                if base_quantity_needed > available_stock:
                    errors.append(
                        f"{item.product.name}: Insufficient stock. "
                        f"Available: {available_stock} base units, "
                        f"Needed: {base_quantity_needed} base units "
                        f"({item.quantity} {item.units.name if item.units else 'units'})"
                    )
                    
            except Exception as e:
                errors.append(f"{item.product.name}: Error checking stock - {str(e)}")
        
        if errors:
            return JsonResponse({
                'success': False,
                'error': 'Stock validation failed',
                'details': errors
            }, status=400)
        
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
        logger.error(f"Error approving transfer request: {str(e)}", exc_info=True)
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
        logger.error(f"Error rejecting transfer request: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'}, status=500)

@login_required
def product_stock_calculation(request, product_id):
    """Calculate available stock after considering requested quantity WITH CONVERSION FACTORS"""
    try:
        product = Product.objects.get(pk=product_id)
        store_id = request.GET.get('store_id')
        requested_qty = Decimal(request.GET.get('requested_qty', '0'))
        unit_id = request.GET.get('unit_id')
        
        if not store_id:
            return JsonResponse({'success': False, 'error': 'Store ID is required'}, status=400)
        
        store = StoreLocation.objects.get(pk=store_id)
        
        # Get conversion factor if unit is specified
        conversion_factor = Decimal('1.0')
        if unit_id:
            try:
                product_unit = ProductUnitPrice.objects.get(
                    product=product,
                    unit_id=unit_id
                )
                conversion_factor = product_unit.conversion_factor
            except ProductUnitPrice.DoesNotExist:
                conversion_factor = Decimal('1.0')
        
        # Calculate base quantity needed
        base_quantity_needed = int(requested_qty * conversion_factor)
        
        # Get current inventory in base units
        try:
            inventory = Inventory.objects.get(product=product, store=store)
            physical_stock = inventory.quantity_in_stock
        except Inventory.DoesNotExist:
            physical_stock = 0
        
        # Calculate committed stock in base units
        committed_stock_base = 0
        committed_items = StockTransferItem.objects.filter(
            product=product,
            stock_transfer__from_store=store,
            stock_transfer__status__in=['pending', 'in_transit']
        ).select_related('units')
        
        for item in committed_items:
            committed_stock_base += item.base_quantity
        
        # Get current request items being edited (if any)
        current_request_id = request.GET.get('current_request_id')
        if current_request_id:
            try:
                current_request = TransferRequest.objects.get(pk=current_request_id)
                # Exclude this request's items from committed stock
                current_request_items = current_request.items.filter(product=product)
                for item in current_request_items:
                    committed_stock_base = max(0, committed_stock_base - item.base_quantity)
            except TransferRequest.DoesNotExist:
                pass
        
        # Calculate available stock in base units
        available_stock_base = max(0, physical_stock - committed_stock_base)
        
        # Calculate remaining stock in base units
        remaining_stock_base = max(0, available_stock_base - base_quantity_needed)
        
        # Calculate display units
        if conversion_factor > 0:
            max_display_units = int(available_stock_base / conversion_factor)
            remaining_display_units = int(remaining_stock_base / conversion_factor)
        else:
            max_display_units = 0
            remaining_display_units = 0
        
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
            'conversion_factor': float(conversion_factor),
            'stock_info': {
                'physical_stock': physical_stock,
                'committed_stock': committed_stock_base,
                'available_stock_base': available_stock_base,
                'available_stock_display': max_display_units,
                'requested_quantity': int(requested_qty),
                'requested_base_quantity': base_quantity_needed,
                'remaining_stock_base': remaining_stock_base,
                'remaining_stock_display': remaining_display_units,
                'base_unit_available': available_stock_base % conversion_factor if conversion_factor > 0 else 0
            },
            'status': 'sufficient' if base_quantity_needed <= available_stock_base else 'insufficient'
        })
        
    except (Product.DoesNotExist, StoreLocation.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Product or Store not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in product stock calculation: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)