from decimal import Decimal
import json
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.paginator import Paginator as BasePaginator
from django.db.models import Prefetch

from app.models.products import Product, ProductUnitPrice, Inventory, StoreLocation, UnitOfMeasure
from app.models.transactions import (
    TransferRequest, TransferRequestItem,
    StockTransfer, StockTransferItem
)
from app.models.human_resource import Department
from app.forms.transaction_forms import (
    TransferRequestForm, TransferRequestItemFormSet,
    StockTransferForm, StockTransferItemFormSet,
    TransferRequestApprovalForm
)
from app.selectors.transfer_selectors import (
    get_all_transfer_requests,
    get_pending_transfer_requests,
    get_stock_transfer_by_id
)
from app.selectors.product_selectors import get_stores, get_all_products, get_all_units_of_measurement
from app.utils.utils import convert_to_base_units, convert_from_base_units, validate_conversion_factor_exists

logger = logging.getLogger(__name__)


def sync_transfer_request_statuses_with_transfers():
    """Keep linked transfer requests aligned with their stock transfer status."""
    linked_transfers = StockTransfer.objects.select_related('transfer_request').filter(
        transfer_request__isnull=False
    )
    requests_to_update = []
    for transfer in linked_transfers:
        tr = transfer.transfer_request
        if tr and tr.status != transfer.status:
            tr.status = transfer.status
            if transfer.status == 'completed' and not tr.fulfilled_date:
                tr.fulfilled_date = timezone.now()
            requests_to_update.append(tr)

    if requests_to_update:
        TransferRequest.objects.bulk_update(requests_to_update, ['status', 'fulfilled_date'])


@login_required
def stock_transfer_list(request):
    status_filter = request.GET.get('status', 'all')
    search = request.GET.get('search', '')
    
    transfers = StockTransfer.objects.select_related(
        'from_store', 'to_store', 'transfer_request', 'created_by'
    ).prefetch_related('items__product')
    
    if status_filter and status_filter != 'all':
        transfers = transfers.filter(status=status_filter)
    
    if search:
        transfers = transfers.filter(
            Q(id__icontains=search) |
            Q(from_store__name__icontains=search) |
            Q(to_store__name__icontains=search) |
            Q(transfer_request__id__icontains=search)
        )
    
    transfers = transfers.order_by('-transfer_date')
    
    status_counts = {
        'pending': StockTransfer.objects.filter(status='pending').count(),
        'in_transit': StockTransfer.objects.filter(status='in_transit').count(),
        'completed': StockTransfer.objects.filter(status='completed').count(),
        'cancelled': StockTransfer.objects.filter(status='cancelled').count(),
    }
    
    pending_approved_requests = TransferRequest.objects.filter(
        status='approved',
        stock_transfers__isnull=True
    ).count()
    
    stock_form = StockTransferForm()
    item_formset = StockTransferItemFormSet(queryset=StockTransferItem.objects.none(), prefix='items')
    stores = get_stores()
    products = get_all_products()
    
    paginator = BasePaginator(transfers, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    total_value = 0
    try:
        from decimal import Decimal
        total_value = Decimal('0.00')
        active_qs = transfers.exclude(status='cancelled')
        for t in active_qs:
            for item in t.items.all():
                try:
                    iv = item.total_value
                    if iv is not None:
                        total_value += Decimal(str(iv))
                except Exception:
                    continue
    except Exception:
        total_value = 0
    
    context = {
        'transfers': page_obj,
        'status_counts': status_counts,
        'pending_approved_requests': pending_approved_requests,
        'total_values': total_value,
        'current_status': status_filter,
        'search_query': search,
        'stock_form': stock_form,
        'item_formset': item_formset,
        'stores': stores,
        'products': products,
        'units': get_all_units_of_measurement()
    }
    
    return render(request, 'transfers/stock_transfer_list.html', context)


@login_required
def stock_transfer_detail(request, transfer_id):
    transfer = get_object_or_404(
        StockTransfer.objects.select_related(
            'from_store', 'to_store', 'transfer_request', 'created_by'
        ).prefetch_related('items__product'),
        id=transfer_id
    )
    
    items_with_conversion = []
    for item in transfer.items.all():
        try:
            base_unit = item.product.unit_prices.filter(conversion_factor=1).first()
            items_with_conversion.append({
                'product': item.product.name,
                'requested': f"{item.quantity} {item.units.name if item.units else ''}",
                'base_units': item.base_quantity,
                'base_unit_name': base_unit.unit.name if base_unit else "base units",
                'conversion': f"1 {item.units.name if item.units else ''} = {item.product.unit_prices.get(unit=item.units).conversion_factor if item.units else 1} {base_unit.unit.name if base_unit else 'base units'}"
            })
        except:
            items_with_conversion.append({
                'product': item.product.name,
                'requested': f"{item.quantity} units",
                'base_units': item.base_quantity,
                'base_unit_name': "base units",
                'conversion': "No conversion factor defined"
            })
    
    context = {
        'transfer': transfer,
        'items': transfer.items.all(),
        'items_with_conversion': items_with_conversion,
        'total_base_units': transfer.total_quantity,
        'total_value': transfer.total_value
    }
    
    return render(request, 'transfers/stock_transfer_detail.html', context)


@login_required
@require_http_methods(["GET"])
def approved_transfer_requests_api(request):
    approved_requests = TransferRequest.objects.filter(
        status='approved',
        stock_transfers__isnull=True
    ).select_related(
        'from_store', 'to_store', 'requested_by', 'approved_by'
    ).prefetch_related('items').order_by('-approved_date')
    
    requests_data = []
    for request in approved_requests:
        requests_data.append({
            'id': request.id,
            'from_store_name': request.from_store.name,
            'to_store_name': request.to_store.name,
            'items_count': request.items.count(),
            'approved_date': request.approved_date.isoformat() if request.approved_date else None,
            'requested_by': request.requested_by.get_full_name() or request.requested_by.username,
            'approved_by': request.approved_by.get_full_name() if request.approved_by else None,
        })
    
    return JsonResponse({
        'success': True,
        'requests': requests_data,
        'count': len(requests_data)
    })


@login_required
@require_http_methods(["POST"])
def update_transfer_status(request, transfer_id):
    try:
        transfer = get_object_or_404(StockTransfer, id=transfer_id)
        
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        new_status = data.get('status')
        comments = data.get('comments', '')
        
        valid_transitions = {
            'pending': ['in_transit', 'cancelled'],
            'in_transit': ['completed', 'cancelled'],
            'completed': [],
            'cancelled': [],
        }
        
        if new_status not in valid_transitions.get(transfer.status, []):
            return JsonResponse({
                'success': False,
                'error': f'Invalid status transition from {transfer.status} to {new_status}'
            }, status=400)
        
        old_status = transfer.status
        transfer.status = new_status
        
        now = timezone.now()
        user_name = request.user.get_full_name() or request.user.username
        if new_status == 'in_transit':
            transfer.started_date = now
            transfer.started_by = user_name
        elif new_status == 'completed':
            transfer.completion_date = now
            transfer.completed_by = user_name
        elif new_status == 'cancelled':
            transfer.cancellation_date = now
            transfer.cancelled_by = user_name
            transfer.cancellation_reason = data.get('cancellation_reason', comments)
        
        transfer.save()

        # ── Sync the linked TransferRequest status ──────────────────────
        if transfer.transfer_request:
            tr = transfer.transfer_request
            tr.status = new_status  # mirror exactly: in_transit, completed, cancelled
            update_fields = ['status']
            if new_status == 'completed':
                tr.fulfilled_date = now
                update_fields.append('fulfilled_date')
            tr.save(update_fields=update_fields)

        if new_status == 'completed' and old_status != 'completed':
            with transaction.atomic():
                transfer.refresh_from_db()
                if transfer.status == 'completed':
                    transfer.apply_inventory_changes()

        return JsonResponse({
            'success': True,
            'message': f'Transfer status updated to {new_status}',
            'new_status': new_status,
            'transfer_request_id': transfer.transfer_request_id,
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def direct_stock_transfer_create(request):
    if request.method == 'POST':
        stock_form = StockTransferForm(request.POST)
        item_formset = StockTransferItemFormSet(request.POST)

        if stock_form.is_valid() and item_formset.is_valid():
            try:
                with transaction.atomic():
                    stock_transfer = stock_form.save(commit=False)
                    stock_transfer.created_by = request.user
                    stock_transfer.transfer_date = timezone.now()
                    stock_transfer.save()

                    items_created = 0
                    validation_errors = []

                    for form in item_formset:
                        if form.is_valid() and form.cleaned_data and not form.cleaned_data.get('DELETE'):
                            product = form.cleaned_data.get('product')
                            quantity = form.cleaned_data.get('quantity')

                            if not product or not quantity:
                                continue

                            transfer_item = form.save(commit=False)
                            transfer_item.stock_transfer = stock_transfer
                            
                            try:
                                inventory = Inventory.objects.get(product=product, store=stock_transfer.from_store)
                                available_stock = inventory.quantity_in_stock
                            except Inventory.DoesNotExist:
                                available_stock = 0

                            if quantity > available_stock:
                                validation_errors.append(
                                    f'Insufficient stock for {product.name}: '
                                    f'Available: {available_stock}, Requested: {quantity}'
                                )
                                continue

                            try:
                                transfer_item.save()
                                items_created += 1
                            except Exception as e:
                                validation_errors.append(f'Error saving item: {str(e)}')
            
                if validation_errors:
                    raise ValidationError('\n'.join(validation_errors))
                
                if items_created == 0:
                    raise ValidationError('At least one valid item must be added to create a transfer.')
                
                messages.success(
                    request, 
                    f'Direct stock transfer # created successfully with {items_created} item(s).'
                )
                return redirect('stock_transfer_list')
                    
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error creating transfer: {str(e)}')
                
        else:
            for field, errors in stock_form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            
            for i, form in enumerate(item_formset):
                if form.errors:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'Item {i+1} - {field}: {error}')
    
    context = {
        'stock_form': StockTransferForm(),
        'item_formset': StockTransferItemFormSet(queryset=StockTransferItem.objects.none()),
        'stores': StoreLocation.objects.filter(is_active=True),
        'products': get_all_products(),
        'is_direct': True
    }
    
    return render(request, 'transfers/stock_transfer_list.html', context)


@login_required
def stock_transfer_create_bulk(request):
    request_ids = request.GET.get('requests', '').split(',')
    
    if not request_ids or request_ids == ['']:
        messages.error(request, 'No requests selected.')
        return redirect('stock_transfer_list')
    
    try:
        approved_requests = TransferRequest.objects.filter(
            id__in=request_ids,
            status='approved',
            stock_transfers__isnull=True
        )
        
        if not approved_requests:
            messages.error(request, 'No valid requests found for bulk creation.')
            return redirect('stock_transfer_list')
        
        if request.method == 'POST':
            created_count = 0
            
            for transfer_request in approved_requests:
                stock_transfer = StockTransfer.objects.create(
                    transfer_request=transfer_request,
                    from_store=transfer_request.from_store,
                    to_store=transfer_request.to_store,
                    created_by=request.user,
                    status='pending'
                )
                
                for request_item in transfer_request.items.all():
                    StockTransferItem.objects.create(
                        stock_transfer=stock_transfer,
                        product=request_item.product,
                        quantity=request_item.quantity,
                        unit_cost=request_item.product.cost_price or 0,
                        units=request_item.units
                    )
                
                created_count += 1
            
            messages.success(
                request, 
                f'Successfully created {created_count} stock transfer{"s" if created_count != 1 else ""}.'
            )
            return redirect('stock_transfer_list')
        
        context = {
            'approved_requests': approved_requests,
            'request_count': len(request_ids),
        }
        
        return redirect('stock_transfer_list')
        
    except Exception as e:
        messages.error(request, f'Error creating bulk transfers: {str(e)}')
        return redirect('stock_transfer_list')


@login_required
def stock_transfer_update(request, transfer_id):
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    
    if transfer.status != 'pending':
        messages.error(request, 'Only pending transfers can be edited.')
        return redirect('stock_transfer_detail', transfer_id=transfer.id)
    
    if request.method == 'POST':
        stock_form = StockTransferForm(request.POST, instance=transfer)
        item_formset = StockTransferItemFormSet(
            request.POST, 
            queryset=transfer.items.all()
        )
        
        if stock_form.is_valid() and item_formset.is_valid():
            try:
                stock_transfer = stock_form.save(commit=False)
                stock_transfer.updated_by = request.user
                stock_transfer.updated_date = timezone.now()
                stock_transfer.save()
                
                items_count = 0
                for form in item_formset:
                    if form.is_valid():
                        if form.cleaned_data.get('DELETE', False):
                            if form.instance.pk:
                                form.instance.delete()
                        elif form.cleaned_data:
                            transfer_item = form.save(commit=False)
                            transfer_item.stock_transfer = stock_transfer
                            
                            if not transfer_item.unit_cost:
                                transfer_item.unit_cost = transfer_item.product.cost_price or 0
                            
                            transfer_item.save()
                            items_count += 1
                
                if items_count == 0:
                    messages.error(request, 'At least one item must remain in the transfer.')
                    return render(request, 'transfers/stock_transfer_form.html', {
                        'stock_form': stock_form,
                        'item_formset': item_formset,
                        'transfer': transfer,
                        'stores': StoreLocation.objects.filter(is_active=True),
                        'is_create': False,
                    })
                
                messages.success(
                    request, 
                    f'Stock transfer #{stock_transfer.id} updated successfully.'
                )
                return redirect('stock_transfer_detail', transfer_id=stock_transfer.id)
                
            except Exception as e:
                messages.error(request, f'Error updating transfer: {str(e)}')
        
        else:
            if not stock_form.is_valid():
                for field, errors in stock_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
            
            if not item_formset.is_valid():
                for i, form in enumerate(item_formset):
                    if form.errors:
                        for field, errors in form.errors.items():
                            for error in errors:
                                messages.error(request, f'Item {i+1} - {field}: {error}')
    
    else:
        stock_form = StockTransferForm(instance=transfer)
        item_formset = StockTransferItemFormSet(queryset=transfer.items.all())
    
    context = {
        'stock_form': stock_form,
        'item_formset': item_formset,
        'transfer': transfer,
        'stores': StoreLocation.objects.filter(is_active=True),
        'is_create': False,
    }
    
    return render(request, 'transfers/stock_transfer_form.html', context)


@login_required
def transfer_request_list(request):
    sync_transfer_request_statuses_with_transfers()
    requests = get_all_transfer_requests()
    departments = Department.objects.filter(is_active=True)
    stores = StoreLocation.objects.filter(is_active=True)
    
    status_counts = {
        'pending': requests.filter(status='pending').count(),
        'approved': requests.filter(status='approved').count(),
        'in_transit': requests.filter(status='in_transit').count(),
        'completed': requests.filter(status='completed').count(),
        'rejected': requests.filter(status='rejected').count(),
        'cancelled': requests.filter(status='cancelled').count(),
        'fulfilled': requests.filter(status='fulfilled').count(),
    }

    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        requests = requests.filter(status=status_filter)

    page = request.GET.get('page', 1)
    paginator = Paginator(requests, 20)
    try:
        requests = paginator.page(page)
    except PageNotAnInteger:
        requests = paginator.page(1)
    except EmptyPage:
        requests = paginator.page(paginator.num_pages)

    request_summaries = []
    for req in requests:
        request_summaries.append({
            'id': req.id,
            'conversion_summary': req.conversion_factor_summary[:200] + "..." if len(req.conversion_factor_summary) > 200 else req.conversion_factor_summary,
            'total_base_units': req.total_requested_items,
            'can_approve': req.can_approve,
            'conversion_details': req.conversion_factor_details
        })

    context = {
        'requests': requests,
        'departments': departments,
        'stores': stores,
        'status_counts': status_counts,
        'current_status': status_filter,
        'form': TransferRequestForm(request=request),
        'formset': TransferRequestItemFormSet(),
        'request_summaries': request_summaries,
    }
    return render(request, 'transfers/transfer_request_list.html', context)


@login_required
def transfer_request_statuses(request):
    sync_transfer_request_statuses_with_transfers()
    ids_param = request.GET.get('ids', '')
    ids = []
    if ids_param:
        for raw_id in ids_param.split(','):
            raw_id = raw_id.strip()
            if raw_id.isdigit():
                ids.append(int(raw_id))

    status_map = {}
    if ids:
        rows = TransferRequest.objects.filter(id__in=ids).values('id', 'status')
        status_map = {str(row['id']): row['status'] for row in rows}

    return JsonResponse({'success': True, 'statuses': status_map})


@login_required
def create_transfer_request(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        
        if data.get('from_store') == data.get('to_store'):
            return JsonResponse({'success': False, 'error': 'Cannot transfer stock to the same store'}, status=400)
        
        required_fields = ['from_store', 'to_store', 'reason']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({'success': False, 'error': f'{field} is required'}, status=400)
        
        if not data.get('items'):
            return JsonResponse({'success': False, 'error': 'At least one item is required'}, status=400)

        from_store = StoreLocation.objects.get(pk=data['from_store'])
        errors = []
        conversion_logs = []

        for i, item in enumerate(data['items']):
            try:
                product = Product.objects.get(pk=item['product_id'])
                unit_id = item.get('units_id')
                
                if not unit_id:
                    errors.append(f"Item {i+1}: Unit is required")
                    continue
                
                try:
                    unit = ProductUnitPrice.objects.get(pk=unit_id).unit
                except ProductUnitPrice.DoesNotExist:
                    errors.append(f"Item {i+1}: Invalid unit selected")
                    continue
                
                validate_conversion_factor_exists(product, unit)
                
                base_qty_needed = convert_to_base_units(product, unit, item['quantity'])
                
                cf_log = f"QTY × CF: {item['quantity']} × {product.unit_prices.get(unit=unit).conversion_factor} = {base_qty_needed} base units"
                conversion_logs.append({
                    'item': i+1,
                    'product': product.name,
                    'calculation': cf_log
                })

                inventory = Inventory.objects.filter(product=product, store=from_store).first()
                physical_stock = inventory.quantity_in_stock if inventory else 0

                committed_stock = StockTransferItem.objects.filter(
                    product=product,
                    stock_transfer__from_store=from_store,
                    stock_transfer__status__in=['pending', 'in_transit']
                ).aggregate(total=Sum('base_quantity'))['total'] or 0

                available_stock = max(0, physical_stock - committed_stock)
                
                if base_qty_needed > available_stock:
                    max_units = convert_from_base_units(product, unit, available_stock)
                    
                    base_unit = product.unit_prices.filter(conversion_factor=1).first()
                    base_unit_name = base_unit.unit.name if base_unit else "base units"
                    
                    errors.append(
                        f"Item {i+1} ({product.name}):\n"
                        f"  Requested: {item['quantity']} {unit.name}\n"
                        f"  Conversion: 1 {unit.name} = {product.unit_prices.get(unit=unit).conversion_factor} {base_unit_name}\n"
                        f"  Base Units Needed: {base_qty_needed} {base_unit_name}\n"
                        f"  Available: {available_stock} {base_unit_name}\n"
                        f"  Shortage: {base_qty_needed - available_stock} {base_unit_name}\n"
                        f"  Max Available: {max_units} {unit.name}"
                    )
                    
            except ValidationError as e:
                errors.append(f"Item {i+1} ({product.name if 'product' in locals() else 'Unknown'}): {str(e)}")
            except Exception as e:
                errors.append(f"Item {i+1}: {str(e)}")

        if errors:
            return JsonResponse({
                'success': False, 
                'error': 'Stock validation failed', 
                'details': errors,
                'conversion_logs': conversion_logs
            }, status=400)

        with transaction.atomic():
            tr = TransferRequest.objects.create(
                requested_by=request.user,
                from_store_id=data['from_store'],
                to_store_id=data['to_store'],
                department_id=data.get('department'),
                priority=data.get('priority', 'normal'),
                required_date=data.get('required_date'),
                note=data.get('reason'),
                status='pending'
            )

            for item in data['items']:
                product = Product.objects.get(pk=item['product_id'])
                unit = ProductUnitPrice.objects.get(pk=item['units_id']).unit
                
                TransferRequestItem.objects.create(
                    transfer_request=tr,
                    product=product,
                    quantity=int(item['quantity']),
                    units=unit,
                    notes=item.get('notes', '')
                )

        tr.refresh_from_db()
        conversion_summary = tr.conversion_factor_summary
        
        return JsonResponse({
            'success': True, 
            'request_id': tr.id, 
            'message': 'Transfer request created successfully',
            'conversion_summary': conversion_summary,
            'conversion_details': tr.conversion_factor_details
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error creating transfer request: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
def update_transfer_request(request, request_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        tr = TransferRequest.objects.get(pk=request_id, requested_by=request.user)
        if tr.status != 'pending':
            return JsonResponse({
                'success': False, 
                'error': 'Cannot edit transfer request that is not pending.'
            })

        data = json.loads(request.body)
        
        if data.get('from_store') == data.get('to_store'):
            return JsonResponse({
                'success': False, 
                'error': 'Cannot transfer stock to the same store'
            }, status=400)
        
        required_fields = ['from_store', 'to_store', 'reason']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False, 
                    'error': f'{field} is required'
                }, status=400)
        
        if not data.get('items'):
            return JsonResponse({
                'success': False, 
                'error': 'At least one item is required'
            }, status=400)

        from_store = StoreLocation.objects.get(pk=data['from_store'])
        errors = []
        conversion_logs = []

        for i, item in enumerate(data['items']):
            try:
                product = Product.objects.get(pk=item['product_id'])
                unit_id = item.get('units_id')
                
                if not unit_id:
                    errors.append(f"Item {i+1}: Unit is required")
                    continue
                
                try:
                    unit = ProductUnitPrice.objects.get(pk=unit_id).unit
                except ProductUnitPrice.DoesNotExist:
                    errors.append(f"Item {i+1}: Invalid unit selected")
                    continue
                
                validate_conversion_factor_exists(product, unit)
                
                base_qty_needed = convert_to_base_units(product, unit, item['quantity'])
                
                cf_log = f"QTY × CF: {item['quantity']} × {product.unit_prices.get(unit=unit).conversion_factor} = {base_qty_needed}"
                conversion_logs.append({
                    'item': i+1,
                    'product': product.name,
                    'calculation': cf_log
                })

                inventory = Inventory.objects.filter(product=product, store=from_store).first()
                physical_stock = inventory.quantity_in_stock if inventory else 0

                committed_stock = StockTransferItem.objects.filter(
                    product=product,
                    stock_transfer__from_store=from_store,
                    stock_transfer__status__in=['pending', 'in_transit']
                ).exclude(stock_transfer__transfer_request=tr).aggregate(
                    total=Sum('base_quantity')
                )['total'] or 0

                available_stock = max(0, physical_stock - committed_stock)
                
                if base_qty_needed > available_stock:
                    max_units = convert_from_base_units(product, unit, available_stock)
                    base_unit = product.unit_prices.filter(conversion_factor=1).first()
                    base_unit_name = base_unit.unit.name if base_unit else "base units"
                    
                    errors.append(
                        f"Item {i+1} ({product.name}):\n"
                        f"  Requested: {item['quantity']} {unit.name}\n"
                        f"  Base Units Needed: {base_qty_needed} {base_unit_name}\n"
                        f"  Available: {available_stock} {base_unit_name}\n"
                        f"  Shortage: {base_qty_needed - available_stock} {base_unit_name}\n"
                        f"  Max Available: {max_units} {unit.name}"
                    )
                    
            except ValidationError as e:
                errors.append(f"Item {i+1} ({product.name if 'product' in locals() else 'Unknown'}): {str(e)}")
            except Exception as e:
                errors.append(f"Item {i+1}: {str(e)}")

        if errors:
            return JsonResponse({
                'success': False, 
                'error': 'Stock validation failed', 
                'details': errors,
                'conversion_logs': conversion_logs
            }, status=400)

        with transaction.atomic():
            tr.from_store_id = data['from_store']
            tr.to_store_id = data['to_store']
            tr.department_id = data.get('department')
            tr.priority = data.get('priority', 'normal')
            tr.required_date = data.get('required_date')
            tr.note = data.get('reason')
            tr.save()

            tr.items.all().delete()
            
            for item in data['items']:
                product = Product.objects.get(pk=item['product_id'])
                unit = ProductUnitPrice.objects.get(pk=item['units_id']).unit
                
                TransferRequestItem.objects.create(
                    transfer_request=tr,
                    product=product,
                    quantity=int(item['quantity']),
                    units=unit,
                    notes=item.get('notes', '')
                )

        tr.refresh_from_db()
        
        return JsonResponse({
            'success': True, 
            'request_id': tr.id, 
            'message': 'Transfer request updated successfully',
            'conversion_summary': tr.conversion_factor_summary,
            'conversion_details': tr.conversion_factor_details,
            'can_approve': tr.can_approve
        })

    except TransferRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transfer request not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error updating transfer request: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def transfer_request_detail(request, request_id):
    tr = get_object_or_404(TransferRequest.objects.select_related(
        'from_store', 'to_store', 'requested_by', 'approved_by', 'department'
    ).prefetch_related(
        Prefetch('items__product', queryset=Product.objects.select_related('category')),
        'items__units'
    ), pk=request_id)
    
    items_with_conversion = []
    for item in tr.items.all():
        item_detail = item.get_display_info()
        
        # Get available stock in source store
        try:
            inventory = Inventory.objects.get(
                product=item.product,
                store=tr.from_store
            )
            available_stock = inventory.quantity_in_stock
        except Inventory.DoesNotExist:
            available_stock = 0
        
        # Check for committed stock
        from app.models.transactions import StockTransferItem
        committed_stock = StockTransferItem.objects.filter(
            product=item.product,
            stock_transfer__from_store=tr.from_store,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('base_quantity'))['committed'] or 0
        
        item_detail['available_in_source'] = max(0, available_stock - committed_stock)
        item_detail['physical_stock'] = available_stock
        item_detail['committed_stock'] = committed_stock
        item_detail['status'] = 'Available' if item.can_be_fulfilled else 'Unavailable'
        
        items_with_conversion.append(item_detail)
    
    stock_report = tr.get_stock_availability_report()
    
    # ADD SKU TO STOCK REPORT ITEMS
    for i, report_item in enumerate(stock_report['items']):
        if i < len(items_with_conversion):
            report_item['sku'] = items_with_conversion[i].get('sku', 'N/A')
        else:
            # Try to get SKU from the actual product
            try:
                transfer_item = tr.items.all()[i]
                report_item['sku'] = transfer_item.product.sku
            except (IndexError, AttributeError):
                report_item['sku'] = 'N/A'
    
    # Get status timeline properly
    status_timeline = [
        {
            'status': 'Request Created',
            'timestamp': tr.request_date,
            'user': tr.requested_by.get_full_name() or tr.requested_by.username
        }
    ]
    
    if tr.status == 'approved' and tr.approved_date:
        status_timeline.append({
            'status': 'Request Approved',
            'timestamp': tr.approved_date,
            'user': tr.approved_by.get_full_name() if tr.approved_by else 'System'
        })
    
    context = {
        'request_obj': tr,
        'items': tr.items.all(),
        'items_with_conversion': items_with_conversion,
        'conversion_summary': tr.conversion_factor_summary,
        'conversion_details': tr.conversion_factor_details,
        'stock_report': stock_report,
        'can_approve': tr.can_approve,
        'total_base_units': tr.total_requested_items,
        'total_estimated_value': tr.total_estimated_value,
        'status_timeline': status_timeline,
    }
    
    return render(request, 'transfers/transfer_request_details.html', context)




@login_required
def approve_transfer_request(request, request_id):
    tr = get_object_or_404(TransferRequest, pk=request_id, status='pending')
    
    if request.method == 'POST':
        action_param = request.POST.get('approve')
        
        if action_param is None:
            return JsonResponse({
                'success': False,
                'error': 'Action not specified'
            }, status=400)
        
        if action_param.lower() in ['true', '1', 'yes', 'on']:
            action = True
        elif action_param.lower() in ['false', '0', 'no', 'off']:
            action = False
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action value'
            }, status=400)
        
        if action:
            if not tr.can_approve:
                return JsonResponse({
                    'success': False,
                    'error': 'Insufficient stock',
                    'message': f'Cannot approve transfer request #{tr.id}. Insufficient stock.'
                }, status=400)
            
            tr.approved_by = request.user
            tr.status = 'approved'
            tr.approved_date = timezone.now()
            
            comments = request.POST.get('comments')
            if comments:
                tr.note = f"{tr.note or ''}\n\nApproval Comments: {comments}"
            
            tr.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Transfer request #{tr.id} approved successfully!',
                'request_id': tr.id,
                'status': 'approved'
            })
            
        else:
            tr.approved_by = request.user
            tr.status = 'rejected'
            tr.approved_date = timezone.now()
            
            comments = request.POST.get('comments')
            if not comments:
                return JsonResponse({
                    'success': False,
                    'error': 'Rejection reason required'
                }, status=400)
            
            tr.note = f"{tr.note or ''}\n\nRejection Reason: {comments}"
            tr.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Transfer request #{tr.id} rejected.',
                'request_id': tr.id,
                'status': 'rejected'
            })
    
    return JsonResponse({
        'success': True,
        'can_approve': tr.can_approve,
        'request': {
            'id': tr.id,
            'from_store': tr.from_store.name if tr.from_store else None,
            'to_store': tr.to_store.name if tr.to_store else None,
            'total_requested_items': tr.total_requested_items,
            'items_count': tr.items.count()
        }
    })


@login_required
def create_stock_transfer(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tr_id = data.get('transfer_request_id')
            
            if tr_id:
                tr = get_object_or_404(TransferRequest, pk=tr_id, status='approved')
                from_store = tr.from_store
                items_data = data.get('items', [])
                
                if not items_data:
                    items_data = []
                    for item in tr.items.all():
                        items_data.append({
                            'product_id': item.product.id,
                            'units_id': item.product.unit_prices.get(unit=item.units).id,
                            'quantity': item.quantity,
                            'notes': item.notes
                        })
            else:
                from_store_id = data.get('from_store')
                if not from_store_id:
                    return JsonResponse({'success': False, 'error': 'From store is required'}, status=400)
                
                from_store = StoreLocation.objects.get(pk=from_store_id)
                items_data = data.get('items', [])
            
            if not items_data:
                return JsonResponse({'success': False, 'error': 'At least one item is required'}, status=400)
            
            errors = []
            conversion_logs = []

            for i, item in enumerate(items_data):
                try:
                    product = Product.objects.get(pk=item['product_id'])
                    unit = ProductUnitPrice.objects.get(pk=item['units_id']).unit
                    
                    validate_conversion_factor_exists(product, unit)
                    
                    base_qty_needed = convert_to_base_units(product, unit, item['quantity'])
                    
                    cf = product.unit_prices.get(unit=unit).conversion_factor
                    conversion_logs.append(
                        f"{product.name}: {item['quantity']} {unit.name} × {cf} = {base_qty_needed} base units"
                    )

                    inventory = Inventory.objects.filter(product=product, store=from_store).first()
                    physical_stock = inventory.quantity_in_stock if inventory else 0

                    committed_stock = StockTransferItem.objects.filter(
                        product=product,
                        stock_transfer__from_store=from_store,
                        stock_transfer__status__in=['pending', 'in_transit']
                    ).aggregate(total=Sum('base_quantity'))['total'] or 0

                    available_stock = max(0, physical_stock - committed_stock)
                    
                    if base_qty_needed > available_stock:
                        max_units = convert_from_base_units(product, unit, available_stock)
                        base_unit = product.unit_prices.filter(conversion_factor=1).first()
                        base_unit_name = base_unit.unit.name if base_unit else "base units"
                        
                        errors.append(
                            f"Item {i+1} ({product.name}):\n"
                            f"  Requested: {item['quantity']} {unit.name}\n"
                            f"  Base Units Needed: {base_qty_needed} {base_unit_name}\n"
                            f"  Available: {available_stock} {base_unit_name}\n"
                            f"  Shortage: {base_qty_needed - available_stock} {base_unit_name}"
                        )
                        
                except ValidationError as e:
                    errors.append(f"Item {i+1}: {str(e)}")
                except Exception as e:
                    errors.append(f"Item {i+1}: {str(e)}")

            if errors:
                return JsonResponse({
                    'success': False, 
                    'error': 'Stock validation failed', 
                    'details': errors,
                    'conversion_logs': conversion_logs
                }, status=400)

            with transaction.atomic():
                if tr_id:
                    st = StockTransfer.objects.create(
                        transfer_request=tr,
                        from_store=tr.from_store,
                        to_store=tr.to_store,
                        created_by=request.user,
                        status='pending'
                    )
                    tr.status = st.status
                    tr.save(update_fields=['status'])
                else:
                    st = StockTransfer.objects.create(
                        from_store_id=data['from_store'],
                        to_store_id=data['to_store'],
                        created_by=request.user,
                        status='pending',
                        note=data.get('note', '')
                    )
                
                for item in items_data:
                    product = Product.objects.get(pk=item['product_id'])
                    unit = ProductUnitPrice.objects.get(pk=item['units_id']).unit
                    
                    StockTransferItem.objects.create(
                        stock_transfer=st,
                        product=product,
                        quantity=int(item['quantity']),
                        units=unit,
                        notes=item.get('notes', '')
                    )
            
            return JsonResponse({
                'success': True, 
                'transfer_id': st.id, 
                'message': 'Stock transfer created successfully',
                'total_base_units': st.total_quantity,
                'conversion_logs': conversion_logs
            })
            
        except Exception as e:
            logger.error(f"Error creating stock transfer: {e}", exc_info=True)
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@login_required
def get_product_units(request, product_id):
    try:
        product = Product.objects.get(pk=product_id)
        units = product.unit_prices.select_related('unit').all()
        
        units_data = []
        for u in units:
            units_data.append({
                'id': u.id,
                'unit_id': u.unit.id,
                'unit_name': u.unit.name,
                'abbreviation': u.unit.abbreviation,
                'conversion_factor': float(u.conversion_factor),
                'price': float(u.price),
                'is_base_unit': u.conversion_factor == 1,
                'conversion_explanation': f"1 {u.unit.name} = {u.conversion_factor} base units"
            })
        
        units_data.sort(key=lambda x: (not x['is_base_unit'], x['conversion_factor']))
        
        base_unit = next((u for u in units_data if u['is_base_unit']), None)
        
        return JsonResponse({
            'success': True, 
            'product': {
                'id': product.id, 
                'name': product.name,
                'sku': product.sku
            }, 
            'units': units_data,
            'base_unit': base_unit,
            'conversion_factors': product.get_conversion_factors()
        })
        
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Product not found'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching product units: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def get_product_stock_for_store(request, product_id, store_id):
    try:
        product = Product.objects.get(pk=product_id)
        store = StoreLocation.objects.get(pk=store_id)
        
        inventory = Inventory.objects.filter(product=product, store=store).first()
        physical_stock = inventory.quantity_in_stock if inventory else 0
        
        stock_transfer_committed = StockTransferItem.objects.filter(
            product=product,
            stock_transfer__from_store=store,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(total=Sum('base_quantity'))
        stock_transfer_committed_qty = stock_transfer_committed['total'] or 0
        
        transfer_request_committed = TransferRequestItem.objects.filter(
            product=product,
            transfer_request__from_store=store,
            transfer_request__status='approved'
        ).aggregate(total=Sum('base_quantity'))
        transfer_request_committed_qty = transfer_request_committed['total'] or 0
        
        total_committed_stock = stock_transfer_committed_qty + transfer_request_committed_qty
        
        available_stock = max(0, physical_stock - total_committed_stock)
        
        base_unit_price = product.unit_prices.filter(conversion_factor=1).first()
        base_unit_info = {
            'name': base_unit_price.unit.name if base_unit_price else "base units",
            'abbreviation': base_unit_price.unit.abbreviation if base_unit_price else "base"
        }
        
        return JsonResponse({
            'success': True,
            'stock': {
                'physical_stock': physical_stock,
                'committed_stock': total_committed_stock,
                'stock_transfer_committed': stock_transfer_committed_qty,
                'transfer_request_committed': transfer_request_committed_qty,
                'available_stock': available_stock,
                'reorder_level': inventory.reorder_level if inventory else 0,
                'unit': base_unit_info['name']
            },
            'product': {
                'id': product.id, 
                'name': product.name,
                'base_unit': base_unit_info
            },
            'store': {'id': store.id, 'name': store.name}
        })
        
    except (Product.DoesNotExist, StoreLocation.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Product or store not found'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching product stock: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def calculate_conversion(request, product_id, unit_id, quantity):
    try:
        product = Product.objects.get(pk=product_id)
        unit_price = ProductUnitPrice.objects.get(pk=unit_id)
        unit = unit_price.unit
        
        try:
            quantity_decimal = Decimal(str(quantity))
        except:
            quantity_decimal = Decimal(0)
        
        base_qty = convert_to_base_units(product, unit, quantity_decimal)
        
        base_unit_price = product.unit_prices.filter(conversion_factor=1).first()
        base_unit_name = base_unit_price.unit.name if base_unit_price else "base units"
        
        display_qty = convert_from_base_units(product, unit, base_qty)
        
        return JsonResponse({
            'success': True,
            'calculation': {
                'formula': f"{quantity_decimal} × {unit_price.conversion_factor} = {base_qty}",
                'explanation': f"{quantity_decimal} {unit.name} × {unit_price.conversion_factor} = {base_qty} {base_unit_name}",
                'base_quantity': float(base_qty),
                'display_quantity': float(display_qty),
                'base_unit': base_unit_name,
                'conversion_factor': float(unit_price.conversion_factor)
            }
        })
        
    except (Product.DoesNotExist, ProductUnitPrice.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Product or unit not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def transfer_request_json(request, request_id):
    try:
        tr = TransferRequest.objects.get(pk=request_id)
        
        items_data = []
        for item in tr.items.all():
            items_data.append({
                'id': item.id,
                'product_id': item.product.id,
                'product_name': item.product.name,
                'quantity': item.quantity,
                'units_id': item.product.unit_prices.get(unit=item.units).id,
                'unit_name': item.units.name,
                'notes': item.notes,
                'base_quantity': item.base_quantity,
                'conversion_factor': float(item.conversion_factor),
                'conversion_explanation': item.conversion_factor_explanation,
                'qty_x_cf_calculation': item.qty_x_cf_calculation
            })
        
        return JsonResponse({
            'success': True,
            'request': {
                'id': tr.id,
                'from_store': tr.from_store.id,
                'from_store_name': tr.from_store.name,
                'to_store': tr.to_store.id,
                'to_store_name': tr.to_store.name,
                'department': tr.department.id if tr.department else None,
                'department_name': tr.department.name if tr.department else None,
                'priority': tr.priority,
                'required_date': tr.required_date.isoformat() if tr.required_date else None,
                'reason': tr.note,
                'status': tr.status,
                'items': items_data,
                'total_base_units': tr.total_requested_items,
                'conversion_summary': tr.conversion_factor_summary,
                'can_approve': tr.can_approve
            }
        })
        
    except TransferRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transfer request not found'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching transfer request JSON: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def create_transfer_from_request(request, request_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        tr = TransferRequest.objects.get(pk=request_id, status='approved')
        
        with transaction.atomic():
            if StockTransfer.objects.filter(transfer_request=tr).exists():
                existing_transfer = StockTransfer.objects.get(transfer_request=tr)
                return JsonResponse({
                    'success': False, 
                    'error': 'Transfer already exists for this request',
                    'transfer_id': existing_transfer.id
                }, status=400)
            
            st = StockTransfer.objects.create(
                transfer_request=tr,
                from_store=tr.from_store,
                to_store=tr.to_store,
                created_by=request.user,
                status='pending',
                note=f"Created from Transfer Request #{tr.id}",
                transfer_date=timezone.now().date()
            )
            
            for request_item in tr.items.all():
                try:
                    unit_price = ProductUnitPrice.objects.get(
                        product=request_item.product,
                        unit=request_item.units
                    )
                    conversion_factor = unit_price.conversion_factor
                except ProductUnitPrice.DoesNotExist:
                    conversion_factor = 1
                
                transfer_item = StockTransferItem.objects.create(
                    stock_transfer=st,
                    product=request_item.product,
                    quantity=request_item.quantity,
                    units=request_item.units,
                )
            
            tr.status = st.status
            tr.save(update_fields=['status'])
        
        try:
            transfer_url = reverse('stock_transfer_detail', kwargs={'transfer_id': st.id})
            full_transfer_url = request.build_absolute_uri(transfer_url)
        except:
            full_transfer_url = f"/transfers/{st.id}/"
        
        return JsonResponse({
            'success': True, 
            'transfer_id': st.id, 
            'message': 'Stock transfer created successfully',
            'total_base_units': st.items.aggregate(total=Sum('base_quantity'))['total'] or 0,
            'conversion_summary': tr.conversion_factor_summary,
            'redirect_url': full_transfer_url
        })
        
    except TransferRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Approved transfer request not found'}, status=404)
    except Exception as e:
        logger.error(f"Error creating transfer from request: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def edit_transfer_request(request, request_id):
    tr = get_object_or_404(TransferRequest, pk=request_id)
    
    if tr.status != 'pending' or tr.requested_by != request.user:
        messages.error(request, "You can only edit your own pending requests")
        return redirect('transfer_request_list')
    
    context = {
        'request_obj': tr,
        'stores': StoreLocation.objects.filter(is_active=True),
        'departments': Department.objects.filter(is_active=True),
        'form': TransferRequestForm(instance=tr, request=request),
        'formset': TransferRequestItemFormSet(instance=tr),
        'conversion_summary': tr.conversion_factor_summary,
        'conversion_details': tr.conversion_factor_details,
        'can_approve': tr.can_approve
    }
    
    return render(request, 'transfers/edit_transfer_request.html', context)


@login_required
def conversion_factor_debug(request, request_id):
    tr = get_object_or_404(TransferRequest, pk=request_id)
    
    debug_info = []
    for i, item in enumerate(tr.items.all(), 1):
        debug_info.append({
            'item_number': i,
            'product': item.product.name,
            'sku': item.product.sku,
            'requested_quantity': item.quantity,
            'requested_unit': item.units.name,
            'conversion_factor': item.conversion_factor,
            'base_quantity': item.base_quantity,
            'calculation': item.qty_x_cf_calculation,
            'available_stock': item.get_available_stock(),
            'can_fulfill': item.can_be_fulfilled,
            'base_unit': item.base_unit_info['name']
        })
    
    context = {
        'transfer_request': tr,
        'debug_info': debug_info,
        'conversion_summary': tr.conversion_factor_summary,
        'total_base_units': tr.total_requested_items
    }
    
    return render(request, 'transfers/conversion_debug.html', context)


@login_required
def print_transfer_request(request, request_id):
    tr = get_object_or_404(TransferRequest, pk=request_id)
    
    context = {
        'request': tr,
        'items': tr.items.all(),
        'conversion_summary': tr.conversion_factor_summary,
        'total_base_units': tr.total_requested_items,
        'total_estimated_value': tr.total_estimated_value,
        'print_mode': True
    }
    
    return render(request, 'transfers/print_transfer_request.html', context)


@login_required
def conversion_help(request):
    return render(request, 'conversion/help.html', {
        'title': 'Conversion Factor Help',
        'examples': [
            {
                'product': 'Sugar Sachets',
                'base_unit': 'Sachet (CF=1)',
                'conversions': [
                    {'unit': 'Pack', 'cf': 10, 'example': '1 Pack = 10 Sachets'},
                    {'unit': 'Box', 'cf': 100, 'example': '1 Box = 100 Sachets'}
                ]
            },
            {
                'product': 'Rice',
                'base_unit': 'Kilogram (CF=1)',
                'conversions': [
                    {'unit': 'Bag', 'cf': 50, 'example': '1 Bag = 50kg'}
                ]
            },
            {
                'product': 'Soda',
                'base_unit': 'Bottle (CF=1)',
                'conversions': [
                    {'unit': 'Crate', 'cf': 24, 'example': '1 Crate = 24 Bottles'}
                ]
            }
        ]
    })


@login_required
def conversion_calculator(request):
    products = Product.objects.filter(is_active=True).prefetch_related('unit_prices', 'unit_prices__unit')
    
    context = {
        'title': 'Conversion Calculator',
        'products': products,
    }
    
    return render(request, 'conversion/calculator.html', context)


@login_required
@require_http_methods(["GET"])
def get_product_info(request, product_id):
    try:
        from app.models.products import Product
        product = get_object_or_404(Product, id=product_id)
        
        from_store_id = request.GET.get('from_store')
        available_stock = 0
        
        if from_store_id:
            try:
                from app.models.products import Inventory
                inventory = Inventory.objects.get(
                    product=product,
                    store_id=from_store_id
                )
                available_stock = inventory.quantity_available
            except Inventory.DoesNotExist:
                available_stock = 0
        
        return JsonResponse({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'cost_price': float(product.cost_price or 0),
                'selling_price': float(product.selling_price or 0),
                'available_stock': available_stock,
                'unit': product.unit or '',
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def validate_transfer_items(request):
    try:
        data = json.loads(request.body)
        from_store_id = data.get('from_store')
        items = data.get('items', [])
        
        if not from_store_id:
            return JsonResponse({
                'success': False,
                'error': 'From store is required'
            })
        
        validation_results = []
        
        for item in items:
            product_id = item.get('product')
            quantity = item.get('quantity', 0)
            
            if not product_id or quantity <= 0:
                continue
            
            try:
                from app.models.products import Product
                from app.models.products import Inventory
                
                product = Product.objects.get(id=product_id)
                
                try:
                    inventory = Inventory.objects.get(
                        product=product,
                        store_id=from_store_id
                    )
                    available = inventory.quantity_available
                except Inventory.DoesNotExist:
                    available = 0
                
                validation_results.append({
                    'product_id': product_id,
                    'product_name': product.name,
                    'requested_quantity': quantity,
                    'available_quantity': available,
                    'is_valid': quantity <= available,
                    'shortage': max(0, quantity - available)
                })
                
            except Product.DoesNotExist:
                validation_results.append({
                    'product_id': product_id,
                    'error': 'Product not found'
                })
        
        return JsonResponse({
            'success': True,
            'validation_results': validation_results
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)