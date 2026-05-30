from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Sum, Q, F
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from app.views.salehelp import *
from app.forms.transaction_forms import SalesForm, SalesItemFormSet
from app.selectors.transaction_selectors import *
from app.selectors.sales_selectors import *
from app.models.transactions import *
from app.models.products import *
from app.models.customers import *

@login_required
def sales_list_view(request):
    # Get filter parameter - default to False (show active sales)
    show_cancelled = request.GET.get('show_cancelled', 'false') == 'true'

    # Use improved selector logic
    sales = get_all_sales(is_cancelled=show_cancelled)

    # Get counts for statistics
    active_count = Sales.objects.filter(is_cancelled=False).count()
    cancelled_count = Sales.objects.filter(is_cancelled=True).count()

    # Calculate statistics for current view
    total_sales_amount = sales.aggregate(total=Sum('total_amount'))['total'] or 0

    if not show_cancelled:
        fulfilled_count = sales.filter(status='FULFILLED').count()
    else:
        fulfilled_count = 0

    # Add pagination
    paginator = Paginator(sales, 25)  # Show 25 sales per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'sales': page_obj.object_list,  # Use current page objects
        'page_obj': page_obj,
        'show_cancelled': show_cancelled,
        'total_sales_amount': total_sales_amount,
        'fulfilled_count': fulfilled_count,
        'cancelled_count': cancelled_count,
        'active_count': active_count,
        'is_paginated': paginator.count > 25,
    }

    return render(request, 'sales/sales_list.html', context)



@login_required
def record_sales_view(request):
    if request.method == 'POST':
        form = SalesForm(request.POST)
        formset = SalesItemFormSet(request.POST, queryset=SalesItem.objects.none())

        # values come as strings → cast to int
        total_amount = int(float(request.POST.get('total_amount', 0)))
        amount_paid = int(float(request.POST.get('amount_paid', 0)))
        amount_received = int(float(request.POST.get('amount_received', 0)))
        
        # Calculate balance (this is what triggers the status logic)
        balance = total_amount - amount_paid

        if form.is_valid() and formset.is_valid():
            sale_data = form.save(commit=False)

            # ---- stock validation ----
            store = sale_data.store
            has_stock_errors = False

            for item_form in formset:
                if item_form.is_valid():
                    product = item_form.cleaned_data.get('product')
                    quantity = item_form.cleaned_data.get('quantity')
                    unit = item_form.cleaned_data.get('unit')

                    if product and quantity and unit:
                        available_stock = get_available_stock_for_product(
                            product.id,
                            store.id
                        )
                        if quantity > available_stock:
                            messages.error(
                                request,
                                f"Insufficient stock for {product.name}. "
                                f"Available: {available_stock}, Requested: {quantity}"
                            )
                            has_stock_errors = True

            if has_stock_errors:
                return render(request, 'sales/record_sales.html', {
                    'form': form,
                    'formset': formset,
                    'products': Product.objects.filter(is_active=True).order_by('name'),
                    'units': UnitOfMeasure.objects.all().order_by('name'),
                })

            try:
                with transaction.atomic():
                    # ---- create sale ----
                    sale = Sales(
                        receipt_no=sale_data.receipt_no,
                        store=sale_data.store,
                        customer=sale_data.customer,
                        total_amount=total_amount,
                        amount_paid=amount_paid,
                        balance=balance,  # This is the key field that determines status
                        amount_received=amount_received,
                        change=sale_data.change,
                        payment_method=sale_data.payment_method,
                        note=sale_data.note,
                        recorded_by=request.user,
                    )
                    sale.save()  # Status will be auto-calculated in the save() method

                    # ---- save items ----
                    sale_items = formset.save(commit=False)
                    for item in sale_items:
                        item.order = sale
                        item.save()
                    
                    # ---- CRITICAL FIX: Create Payment record if amount_paid > 0 ----
                    if amount_paid > 0 and sale.payment_method and sale.customer:
                        Payment.objects.create(
                            customer=sale.customer,
                            amount=amount_paid,
                            payment_method=sale.payment_method,
                            reference=sale.receipt_no,
                            note=f"Payment for sale {sale.receipt_no}",
                            payment_date=timezone.now()
                        )
                        # Signal will automatically create ledger entry for this payment

            except Exception as e:
                messages.error(request, f"Failed to save sale: {e}")
                return render(request, 'sales/record_sales.html', {
                    'form': form,
                    'formset': formset,
                    'products': Product.objects.filter(is_active=True).order_by('name'),
                    'units': UnitOfMeasure.objects.all().order_by('name'),
                })

            messages.success(
                request,
                f"Sale #{sale.receipt_no} created successfully "
                f"with status: {sale.get_status_display()}."
            )
            return redirect('sales_list')

        # ---- form errors ----
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")

        for item_form in formset:
            for field, errors in item_form.errors.items():
                for error in errors:
                    messages.error(
                        request,
                        f"Item {item_form.prefix} - {field}: {error}"
                    )

    else:
        form = SalesForm()
        formset = SalesItemFormSet(queryset=SalesItem.objects.none())

    return render(request, 'sales/record_sales.html', {
        'form': form,
        'formset': formset,
        'products': Product.objects.filter(is_active=True).order_by('name'),
        'units': UnitOfMeasure.objects.all().order_by('name'),
    })


# def update_inventory_after_sale(sale, sale_items):
#     """
#     Update inventory after a successful sale
#     """
#     try:
#         with transaction.atomic():
#             for item in sale_items:
#                 # Get inventory for this product in this store
#                 inventory, created = Inventory.objects.get_or_create(
#                     product=item.product,
#                     store=sale.store,
#                     defaults={'quantity_in_stock': 0}
#                 )
                
#                 # Deduct sold quantity from inventory
#                 old_stock = inventory.quantity_in_stock
#                 inventory.quantity_in_stock = F('quantity_in_stock') - item.quantity
#                 inventory.save()
#                 inventory.refresh_from_db()
                
#                 # Create stock movement record
#                 StockMovement.objects.create(
#                     product=item.product,
#                     store=sale.store,
#                     transaction_type='SALE',
#                     quantity=-item.quantity,  # Negative for deduction
#                     transaction_id=sale.id,
#                     note=f"Sale #{sale.receipt_no}",
#                     units_in_stock=inventory.quantity_in_stock,
#                     user=str(sale.recorded_by)
#                 )
                
#                 # Update inventory batches using FIFO
#                 update_inventory_batches_after_sale(item.product, sale.store, item.quantity)
                
#     except Exception as e:
#         raise Exception(f"Inventory update failed: {str(e)}")

def update_inventory_batches_after_sale(product, store, quantity_sold):
    """
    Update inventory batches using FIFO method
    """
    # Get non-expired batches ordered by expiry date (FIFO)
    batches = InventoryBatch.objects.filter(
        product=product,
        store=store,
        remaining_quantity__gt=0
    ).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.now().date()))
    
    batches = batches.order_by('expiry_date', 'received_date')
    
    remaining_to_deduct = quantity_sold
    
    for batch in batches:
        if remaining_to_deduct <= 0:
            break
            
        if batch.remaining_quantity >= remaining_to_deduct:
            batch.remaining_quantity = F('remaining_quantity') - remaining_to_deduct
            batch.save()
            remaining_to_deduct = 0
        else:
            remaining_to_deduct -= batch.remaining_quantity
            batch.remaining_quantity = 0
            batch.save()




@login_required
def sales_detail_view(request, pk):
    sale = get_object_or_404(Sales, pk=pk)
    items = get_sales_items_for_sale(sale)
    
    # Get stock movement records for this sale (for cancelled sales)
    stock_movements = []
    if sale.is_cancelled:
        stock_movements = StockMovement.objects.filter(
            transaction_id=sale.id,
            transaction_type__in=['SALE', 'CANCELLATION']
        ).order_by('-timestamp')
    
    context = {
        'sale': sale,
        'items': items,
        'stock_movements': stock_movements,
    }
    return render(request, 'sales/sales_detail.html', context)


@login_required
def sales_update_view(request, pk):
    sale = get_object_or_404(Sales, pk=pk)
    
    # Don't allow updating cancelled sales
    if sale.is_cancelled:
        messages.error(request, f"Cannot update cancelled sale #{sale.receipt_no}.")
        return redirect('sales_list')
    
    if request.method == 'POST':
        form = SalesForm(request.POST, instance=sale)
        formset = SalesItemFormSet(request.POST, queryset=get_sales_items_for_sale(sale))
        
        total_amount = int(float(request.POST.get('total_amount', 0)))
        amount_paid = int(float(request.POST.get('amount_paid', 0)))
        balance = total_amount - amount_paid
        
        if form.is_valid() and formset.is_valid():
            sale = form.save(commit=False)
            
            # Validate stock availability for updates
            store = sale.store
            has_stock_errors = False
            
            for formset_form in formset:
                if formset_form.is_valid() and not formset_form.cleaned_data.get('DELETE', False):
                    product = formset_form.cleaned_data.get('product')
                    quantity = formset_form.cleaned_data.get('quantity')
                    unit = formset_form.cleaned_data.get('unit')
                    
                    if product and quantity and unit:
                        # Get available stock plus what's already in this sale
                        available_stock = get_available_stock_for_product(product.id, store.id)
                        
                        # If editing, add back the existing quantity from this sale
                        existing_item = formset_form.instance
                        if existing_item and existing_item.id:
                            existing_quantity = existing_item.quantity
                            available_stock += existing_quantity
                        
                        if quantity > available_stock:
                            messages.error(request, f"Insufficient stock for {product.name}. Available: {available_stock}, Requested: {quantity}")
                            has_stock_errors = True
            
            if has_stock_errors:
                # Re-render form with stock errors
                products = Product.objects.filter(is_active=True).order_by('name')
                units = UnitOfMeasure.objects.all().order_by('name')
                context = {
                    'form': form,
                    'formset': formset,
                    'sale': sale,
                    'products': products,
                    'units': units,
                }
                return render(request, 'sales/record_sales.html', context)
            
            try:
                with transaction.atomic():
                    # Update sale amounts - the status will be auto-calculated on save
                    sale.total_amount = total_amount
                    sale.amount_paid = amount_paid
                    sale.balance = balance  # This triggers the status logic
                    
                    # Set recorded_by to current user (or keep original if not changing)
                    sale.recorded_by = request.user
                    sale.save()  # Status will be updated here
                    
                    # Save sale items
                    sale_items = formset.save(commit=False)
                    for item in sale_items:
                        item.order = sale
                        item.save()
                    
                    # Delete removed items
                    for obj in formset.deleted_objects:
                        obj.delete()
                    
                    # NOTE: Inventory updates are now handled by signals
                    # When SalesItems are saved/deleted, signals will automatically
                    # update inventory accordingly
                    
            except Exception as e:
                messages.error(request, f"Failed to update sale: {e}")
                return render(request, 'sales/record_sales.html', {
                    'form': form,
                    'formset': formset,
                    'sale': sale,
                    'products': Product.objects.filter(is_active=True).order_by('name'),
                    'units': UnitOfMeasure.objects.all().order_by('name'),
                })
            
            messages.success(request, f'Sale #{sale.receipt_no} updated successfully. Status: {sale.get_status_display()}')
            return redirect('sales_list')
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

            for item_form in formset:
                for field, errors in item_form.errors.items():
                    for error in errors:
                        messages.error(
                            request,
                            f"Item {item_form.prefix} - {field}: {error}"
                        )
    else:
        form = SalesForm(instance=sale)
        formset = SalesItemFormSet(queryset=get_sales_items_for_sale(sale))
    
    # Get products and units for the template
    products = Product.objects.filter(is_active=True).order_by('name')
    units = UnitOfMeasure.objects.all().order_by('name')
    
    context = {
        'form': form,
        'formset': formset,
        'sale': sale,
        'products': products,
        'units': units,
    }
    return render(request, 'sales/record_sales.html', context)




@login_required
def sales_delete_view(request, pk):
    sale = get_object_or_404(Sales, pk=pk)
   
    receipt_no = sale.receipt_no
    sale.delete()
    messages.success(request, f'Sale #{receipt_no} deleted successfully.')
        
    return redirect('sales_list')

@login_required
@transaction.atomic
def cancel_sale_view(request, pk):
    """
    Cancel a sale and return stock to inventory
    """
    sale = get_object_or_404(Sales, pk=pk)
    
    # Check if sale is already cancelled
    if sale.is_cancelled:
        messages.warning(request, f"Sale #{sale.receipt_no} is already cancelled.")
        return redirect('sales_list')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        
        if not reason:
            messages.error(request, "Please provide a reason for cancellation.")
            return redirect('sales_detail', pk=pk)
        
        try:
            # Use the model's cancel_sale method
            success, message = sale.cancel_sale(request.user, reason)
            
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)
                
        except Exception as e:
            messages.error(request, f"Failed to cancel sale: {str(e)}")
        
        return redirect('sales_list')
    
    # If GET request, redirect to detail page
    return redirect('sales_detail', pk=pk)


# Helper function to get available stock
def get_available_stock_for_product(product_id, store_id):
    """
    Calculate available stock for a product in a specific store
    """
    try:
        # Get physical stock from Inventory
        inventory = Inventory.objects.filter(
            product_id=product_id,
            store_id=store_id
        ).first()
        
        physical_stock = inventory.quantity_in_stock if inventory else 0
        
        # Calculate committed stock from pending/in-transit transfers
        committed_stock = StockTransferItem.objects.filter(
            product_id=product_id,
            stock_transfer__from_store_id=store_id,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
        # Calculate committed stock from pending sales (excluding current sale)
        pending_sales_stock = SalesItem.objects.filter(
            product_id=product_id,
            order__store_id=store_id,
            order__status__in=['PENDING', 'PARTIALLY_PAID'],
            order__is_cancelled=False  # Exclude cancelled sales
        ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
        available_stock = max(0, physical_stock - committed_stock - pending_sales_stock)
        
        return available_stock
        
    except Exception as e:
        print(f"Error calculating available stock: {e}")
        return 0

# API endpoint for product stock and price information
@login_required
@require_GET
def get_product_stock_info(request, product_id):
    """
    API endpoint to get product stock information and unit prices
    """
    store_id = request.GET.get('store_id')
    
    if not store_id:
        return JsonResponse({
            'success': False,
            'error': 'Store ID is required',
            'available_stock': 0,
            'physical_stock': 0,
            'committed_stock': 0,
            'unit_prices': []
        })
    
    try:
        product = Product.objects.get(id=product_id)
        
        # Get physical stock from Inventory
        inventory = Inventory.objects.filter(
            product=product,
            store_id=store_id
        ).first()
        
        physical_stock = inventory.quantity_in_stock if inventory else 0
        
        # Calculate committed stock from pending/in-transit transfers
        committed_transfer_stock = StockTransferItem.objects.filter(
            product=product,
            stock_transfer__from_store_id=store_id,
            stock_transfer__status__in=['in_transit']
        ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
        committed_stock = committed_transfer_stock

        available_stock = max(0, physical_stock - committed_stock)
        
        # Get unit prices with conversion factors
        unit_prices = []
        for up in product.unit_prices.all().order_by('conversion_factor'):
            unit_prices.append({
                'unit_id': up.unit.id,
                'unit_name': up.unit.name,
                'abbreviation': up.unit.abbreviation,
                'price': str(up.price),
                'conversion_factor': up.conversion_factor
            })
        
        return JsonResponse({
            'success': True,
            'available_stock': available_stock,
            'physical_stock': physical_stock,
            'committed_stock': committed_stock,
            'unit_prices': unit_prices,
            'product_name': product.name,
            'product_sku': product.sku,
            'store_id': store_id
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found',
            'available_stock': 0,
            'unit_prices': []
        }, status=404)
    except Exception as e:
        print(f"Error in get_product_stock_info: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'available_stock': 0,
            'unit_prices': []
        }, status=500)


@login_required
@require_GET
def get_product_by_barcode(request):
    barcode = request.GET.get('barcode', '').strip()
    if not barcode:
        return JsonResponse({'success': False, 'error': 'Barcode is required'}, status=400)

    product = Product.objects.filter(
        is_active=True
    ).filter(
        Q(barcode=barcode) | Q(sku=barcode)
    ).first()

    if not product:
        return JsonResponse({'success': False, 'error': 'No product found for this barcode'}, status=404)

    return JsonResponse({
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'barcode': product.barcode,
        }
    })

# API endpoint for product autocomplete
@login_required
@require_GET
def product_autocomplete(request):
    """
    API endpoint for product autocomplete search
    """
    query = request.GET.get('term', '')
    store_id = request.GET.get('store_id', '')
    
    # Base queryset
    products_qs = Product.objects.filter(is_active=True)
    
    # Apply search filter
    if query:
        products_qs = products_qs.filter(
            Q(name__icontains=query) | 
            Q(sku__icontains=query) | 
            Q(barcode__icontains=query)
        )
    
    # Limit results
    products_qs = products_qs[:20]
    
    results = []
    for product in products_qs:
        # Get available stock for the store if store_id is provided
        available_stock = None
        if store_id:
            available_stock = get_available_stock_for_product(product.id, store_id)
        
        # Get default unit price
        default_unit_price = product.unit_prices.order_by('id').first()
        default_price = default_unit_price.price if default_unit_price else 0
        
        results.append({
            'id': product.id,
            'label': f"{product.name} ({product.sku})",
            'value': product.name,
            'sku': product.sku,
            'barcode': product.barcode or '',
            'default_price': str(default_price),
            'available_stock': available_stock,
            'has_stock': available_stock > 0 if available_stock is not None else True
        })
    
    return JsonResponse(results, safe=False)

# API endpoint to get all products for dropdown
@login_required
@require_GET
def get_products_list(request):
    """
    API endpoint to get all active products for dropdown
    """
    try:
        products = Product.objects.filter(is_active=True).order_by('name')
        
        product_list = []
        for product in products:
            product_list.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'barcode': product.barcode,
                'category': product.category.name if product.category else '',
                'brand': product.brand or ''
            })
        
        return JsonResponse({
            'success': True,
            'products': product_list,
            'count': len(product_list)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'products': []
        }, status=500)

# API endpoint to get all units for dropdown
@login_required
@require_GET
def get_units_list(request):
    """
    API endpoint to get all units of measure for dropdown
    """
    try:
        units = UnitOfMeasure.objects.all().order_by('name')
        
        unit_list = []
        for unit in units:
            unit_list.append({
                'id': unit.id,
                'name': unit.name,
                'abbreviation': unit.abbreviation
            })
        
        return JsonResponse({
            'success': True,
            'units': unit_list,
            'count': len(unit_list)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'units': []
        }, status=500)

# API endpoint to validate sale before submission
@login_required
@require_GET
def validate_sale_stock(request):
    """
    API endpoint to validate stock availability before sale submission
    """
    try:
        store_id = request.GET.get('store_id')
        items_json = request.GET.get('items', '[]')
        
        if not store_id:
            return JsonResponse({
                'success': False,
                'error': 'Store ID is required'
            })
        
        import json
        items = json.loads(items_json)
        
        validation_results = []
        all_valid = True
        
        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 0)
            
            if product_id and quantity > 0:
                available_stock = get_available_stock_for_product(product_id, store_id)
                
                is_valid = quantity <= available_stock
                all_valid = all_valid and is_valid
                
                validation_results.append({
                    'product_id': product_id,
                    'quantity': quantity,
                    'available_stock': available_stock,
                    'is_valid': is_valid,
                    'message': f"Available: {available_stock}, Requested: {quantity}"
                })
        
        return JsonResponse({
            'success': True,
            'all_valid': all_valid,
            'validation_results': validation_results
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# API endpoint to get product details
@login_required
@require_GET
def get_product_details(request, product_id):
    """
    API endpoint to get detailed product information
    """
    try:
        product = Product.objects.get(id=product_id)
        
        # Get all unit prices
        unit_prices = []
        for up in product.unit_prices.all().order_by('conversion_factor'):
            unit_prices.append({
                'unit_id': up.unit.id,
                'unit_name': up.unit.name,
                'abbreviation': up.unit.abbreviation,
                'price': str(up.price),
                'conversion_factor': up.conversion_factor
            })
        
        # Get stock information for all stores
        stock_by_store = []
        for inventory in product.inventories.all():
            store = inventory.store
            available_stock = get_available_stock_for_product(product.id, store.id)
            
            stock_by_store.append({
                'store_id': store.id,
                'store_name': store.name,
                'physical_stock': inventory.quantity_in_stock,
                'available_stock': available_stock,
                'reorder_level': inventory.reorder_level
            })
        
        return JsonResponse({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'barcode': product.barcode,
                'brand': product.brand,
                'category': product.category.name if product.category else '',
                'description': product.description or '',
                'is_active': product.is_active
            },
            'unit_prices': unit_prices,
            'stock_by_store': stock_by_store,
            'total_stock': product.total_stock
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
 
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        