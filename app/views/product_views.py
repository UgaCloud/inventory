from django.shortcuts import (
    render, redirect, 
    get_object_or_404, HttpResponseRedirect
)
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import csv
from django.http import HttpResponse, JsonResponse

from app.forms.product_forms import *
from app.forms.transaction_forms import StockAdjustmentForm
from app.selectors.product_selectors import *
from app.models.products import *

from django.db.models import Q
import csv
from django.utils import timezone
from app.models.products import Inventory
from app.models.transactions import StockTransferItem
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.csrf import csrf_exempt
import json



@login_required
def manage_product_view(request):
    product_form = ProductForm()

    # Get all products with filtering support
    products = Product.objects.select_related('category').all().order_by('id')
    
    # Apply filters from query parameters
    category_id = request.GET.get('category')
    brand_filter = request.GET.get('brand')
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status')
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    if brand_filter:
        products = products.filter(brand__iexact=brand_filter)
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)
    
    # Get all categories for dropdown
    categories = Category.objects.all()
    
    # Get all unique brands for dropdown
    brands = Product.objects.exclude(
        brand__isnull=True
    ).exclude(
        brand=''
    ).values_list('brand', flat=True).distinct().order_by('brand')
    
    # Create edit forms for each product
    edit_forms = {}
    
    # Process ALL products (no pagination - we'll do client-side pagination)
    enhanced_products = []
    products_list = list(products)  # Convert to list for processing
    
    for product in products_list:
        total_committed_stock = StockTransferItem.objects.filter(
            product=product,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
        total_physical_stock = sum(inv.quantity_in_stock for inv in product.inventories.all())
        total_available_stock = total_physical_stock - total_committed_stock
        
        # Create edit form for each product
        edit_forms[product.id] = ProductForm(instance=product)
        
        enhanced_products.append({
            'product': product,
            'total_physical_stock': total_physical_stock,
            'total_committed_stock': total_committed_stock,
            'total_available_stock': max(0, total_available_stock),
            'edit_form': edit_forms[product.id],
        })
    
    # Convert to JSON for client-side
    products_json = []
    for item in enhanced_products:
        product = item['product']
        products_json.append({
            'id': product.id,
            'name': product.name,
            'sku': product.sku or '',
            'brand': product.brand or '',
            'is_active': product.is_active,
            'default_price': float(product.default_price) if product.default_price else 0,
            'default_unit': str(product.default_unit) if product.default_unit else '',
            'category_name': product.category.name if product.category else None,
            'category_id': product.category.id if product.category else None,
            'total_available_stock': item['total_available_stock'],
            'unit_count': 0,  # You can calculate this if needed
            'total_physical_stock': item['total_physical_stock'],
            'total_committed_stock': item['total_committed_stock']
        })
    
    automotives = Automotive.objects.all()
    context = {
        'form': product_form,
        'products': enhanced_products,  # For edit modals
        'products_json': json.dumps(products_json),  # For client-side pagination
        'categories': categories,
        'brands': brands,
        'automotives': automotives,
        'selected_category': category_id,
        'selected_brand': brand_filter,
        'search_query': search_query,
        'selected_status': status_filter,
    }
    return render(request, 'products/products.html', context)






@login_required
def add_product_view(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product added successfully!')
            return redirect('products_page')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProductForm()
    
    # If there are errors, return to the products page with the form
    products = get_all_products()
    categories = get_all_categories()
    
    enhanced_products = []
    for product in products:
        total_committed_stock = StockTransferItem.objects.filter(
            product=product,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
        total_physical_stock = sum(inv.quantity_in_stock for inv in product.inventories.all())
        total_available_stock = max(0, total_physical_stock - total_committed_stock)
        
        enhanced_products.append({
            'product': product,
            'total_physical_stock': total_physical_stock,
            'total_committed_stock': total_committed_stock,
            'total_available_stock': total_available_stock,
        })

    context = {
        'form': form,  # Pass the form with errors
        'products': enhanced_products,
        'categories': categories,
        'is_admin': request.user.is_staff or request.user.is_superuser,
    }
    return render(request, 'products/products.html', context)


@login_required
def edit_product_view(request, product_id):
    product = get_product_by_id(product_id)

    if request.method == "POST":
        edit_form = ProductForm(request.POST, instance=product)
        
        if edit_form.is_valid():
            edit_form.save()
            messages.success(request, f'Product "{product.name}" has been updated successfully.')
            return redirect('product_details_page', _product_id=product.id)
        else:
            messages.error(request, 'Please correct the errors below.')
            # Render form with errors
            context = {
                'edit_form': edit_form,
                'product': product,
            }
            return render(request, 'products/edit_product.html', context)
    
    # GET request - show edit form
    edit_form = ProductForm(instance=product)
    
    context = {
        'edit_form': edit_form,
        'product': product,
    }
    return render(request, 'products/edit_product.html', context)


@login_required
def delete_product_view(request, product_id):
    """Delete a product - only accessible to superusers and admins"""
    if not (request.user.is_superuser or request.user.groups.filter(name='Admin').exists()):
        messages.error(request, 'You do not have permission to delete products.')
        return redirect('products_page')
    
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Product "{product_name}" has been deleted successfully.')
        return redirect('products_page')
    
    # If GET request, show confirmation (handled by modal in template)
    return redirect('products_page')


@login_required
def add_category_view(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Category added successfully.')
            return redirect(add_category_view)
        else:
            messages.error(request, 'There was an error adding the category.')
    else:
        form = CategoryForm()
        categories = get_all_categories()

    context = {
        'form':form,
        'categories': categories
    }

    return render(request, 'products/add_category.html', context)

@login_required
def edit_category_view(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Store updated successfully.")
            return redirect(add_category_view)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryForm(instance=category)
    return redirect(add_category_view)


@login_required
def delete_category_view(request, category_id):
    category = get_category_by_id(category_id)
    category.delete()
    messages.success(request, 'Category deleted successfully.')
    return redirect(manage_product_view)

@login_required
def unit_of_measure_view(request):

    if request.method == 'POST':
        form = UnitOfMeasureForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Unit of measure added successfully.')
        else:
            messages.error(request, 'There was an error adding the unit of measure.')
    else:
        form = UnitOfMeasureForm()

    units_of_measurement = get_all_units_of_measurement()
    
    context = {
        'form':form,
        'units_of_measurement':units_of_measurement
    }
    
    return render(request, 'products/unit_of_measure.html', context)

@login_required
def edit_unit_of_measure_view(request, unit_id):
    unit = get_object_or_404(UnitOfMeasure, id=unit_id)
    if request.method == 'POST':
        form = UnitOfMeasureForm(request.POST, instance=unit)
        if form.is_valid():
            form.save()
            messages.success(request, "Unit of Measure updated successfully.")
            return redirect(unit_of_measure_view)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryForm(instance=unit)
    return redirect(unit_of_measure_view)


@login_required
def get_product_units_json(request, product_id):
    """API endpoint to get product units for modal display"""
    try:
        product = get_product_by_id(product_id=product_id)
        units = product.unit_prices.all().order_by('conversion_factor')
        
        units_data = []
        for unit in units:
            # Determine if this is the base unit (conversion_factor == 1)
            is_base_unit = unit.conversion_factor == 1
            
            units_data.append({
                'id': unit.id,
                'unit_name': unit.unit.name if unit.unit else 'N/A',
                'abbreviation': unit.unit.abbreviation if unit.unit else 'N/A',
                'conversion_factor': float(unit.conversion_factor),  # Convert to float for JSON
                'price': float(unit.price),  # Convert to float
                'is_base_unit': is_base_unit,  # Calculated based on conversion_factor
                'unit': {
                    'name': unit.unit.name if unit.unit else '',
                    'abbreviation': unit.unit.abbreviation if unit.unit else ''
                }
            })
        
        return JsonResponse({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'sku': product.sku
            },
            'units': units_data,
            'total_units': len(units_data)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()  # This will print the full traceback to console
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def product_details_view(request, _product_id):

    item = get_product_by_id(product_id=_product_id)
    product_form = ProductForm(instance=item)
    product_unit_price_form = ProductUnitPriceForm(initial={'product':item})
    inventory_form = InventoryForm(initial={'product': item})
    product_unit_prices = item.unit_prices.all()
    inventories = item.inventories.all()

    # Store filter
    from app.models.products import StoreLocation
    stores = StoreLocation.objects.filter(is_active=True)
    selected_store_id = request.GET.get('store')
    selected_store = None
    if selected_store_id:
        try:
            selected_store = StoreLocation.objects.get(id=selected_store_id)
        except StoreLocation.DoesNotExist:
            selected_store = None

    if selected_store:
        stock_movements = item.stock_movements.filter(store=selected_store)
    else:
        stock_movements = item.stock_movements.all()

    units = get_all_units_of_measurement()
    
    # Debug: Check for inventory records with missing store IDs
    for inventory in inventories:
        if not inventory.store or not inventory.store.id:
            print(f"Warning: Inventory {inventory.id} has missing store information")
    
    # NEW: Calculate real-time stock data for each inventory
    inventory_data = []
    for inventory in inventories:
        # Calculate committed stock for this store
        committed_stock = StockTransferItem.objects.filter(
            product=item,
            stock_transfer__from_store=inventory.store,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
        
        # available_stock = inventory.quantity_in_stock
        available_stock = max(0, inventory.quantity_in_stock - committed_stock)
        
        inventory_data.append({
            'inventory': inventory,
            'committed_stock': committed_stock,
            'available_stock': available_stock,
            'status': 'out_of_stock' if available_stock == 0 else 
                     'low_stock' if available_stock <= (inventory.reorder_level or 0) else 
                     'in_stock'
        })

    stock_adjustment_form = StockAdjustmentForm(initial={'product': item})

    context = {
        'product_form': product_form,
        'product_unit_price_form': product_unit_price_form,
        'inventory_form': inventory_form,
        'product': item,
        'unit_prices': product_unit_prices,
        'inventories': inventory_data,  # Updated to include real-time data
        'stock_movements': stock_movements,
        'units': units,
        'stock_adjustment_form': stock_adjustment_form,
        'units': units,
        'total_physical_stock': sum(inv.quantity_in_stock for inv in inventories),
        'total_committed_stock': sum(data['committed_stock'] for data in inventory_data),
        'total_available_stock': sum(data['available_stock'] for data in inventory_data),
        'stores': stores,
        'selected_store': selected_store,
    }
    return render(request, 'products/product_details.html', context)

@login_required
def add_product_unit_price_view(request):
    if request.method == 'POST':
        form = ProductUnitPriceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product unit price added successfully.')
            return redirect(product_details_view, request.POST.get('product'))
        else:
            messages.error(request, form.errors)
            
            return redirect(product_details_view, request.POST.get('product'))
    else:
        pass

def update_product_unit_price_view(request, pup_id):
    pup = get_object_or_404(ProductUnitPrice, id=pup_id)
    
    if request.method == 'POST':
        # Create a mutable copy of POST data
        post_data = request.POST.copy()
        
        # Make sure the product field is set to pup.product.id
        # This ensures it's always in the POST data even if hidden field wasn't submitted
        post_data['product'] = str(pup.product.id)
        
        form = ProductUnitPriceForm(post_data, instance=pup)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Product unit price updated successfully.')
            return redirect(product_details_view, pup.product.id)
        else:
            # Format errors for display
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_messages.append(f"{field}: {error}")
            messages.error(request, ' | '.join(error_messages))
            return redirect(product_details_view, pup.product.id)
    else:
        # Handle GET requests - redirect to product details page
        # Or render an edit form if you have one
        return redirect(product_details_view, pup.product.id)

@login_required
def add_inventory_view(request):
    if request.method == 'POST':
        form = InventoryForm(request.POST)

        if form.is_valid():
            form.save()
  
    return redirect(product_details_view, request.POST.get('product'))

@login_required
def store_view(request):
    
    if request.method == "POST":
        form = StoreLocationForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Store location added successfully.')
        else:
            messages.error(request, 'There was an error adding the store location.')
    form = StoreLocationForm()
    stores = StoreLocation.objects.all()

    context = {
        'store_form':form,
        'stores': stores
        
    }
    return render(request, 'products/store.html', context)

@login_required
def edit_store_view(request, store_id):
    store = get_object_or_404(StoreLocation, id=store_id)
    if request.method == 'POST':
        form = StoreLocationForm(request.POST, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, "Store updated successfully.")
            return redirect(store_view)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StoreLocationForm(instance=store)
    return redirect(store_view)


@login_required
def bulk_add_categories_view(request):
    """
    Allows bulk creation of categories via CSV upload (columns: name, description).
    """
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)
        created, errors = 0, []
        for row in reader:
            name = row.get('name')
            description = row.get('description', '')
            if name:
                Category.objects.get_or_create(name=name, defaults={'description': description})
                created += 1
            else:
                errors.append(row)
        if errors:
            messages.warning(request, f"Some rows were skipped due to missing name: {errors}")
        messages.success(request, f"{created} categories added successfully.")
        return redirect(add_category_view)
    return render(request, 'products/bulk_add_categories.html')

@login_required
def download_category_template_view(request):
    """
    Provides a CSV template for bulk category upload.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="category_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['name', 'description'])
    writer.writerow(['Example Category', 'Optional description'])
    return response

@login_required
def bulk_add_products_view(request):
    """
    Allows bulk creation of products via CSV upload (columns: name, brand, description, barcode, category, is_active).
    Category should match an existing category name.
    SKU will be auto-generated if not provided, using the Product model's save() logic.
    """
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)
        created, errors = 0, []
        for row in reader:
            name = row.get('name')
            brand = row.get('brand', '')
            description = row.get('description', '')
            category_name = row.get('category')
            is_active = row.get('is_active', 'True').lower() in ['true', '1', 'yes']
            category = None
            if category_name:
                category = Category.objects.filter(name=category_name).first()
            if name and category:
                # Do not set SKU, let Product.save() auto-generate it
                Product.objects.get_or_create(
                    name=name,
                    defaults={
                        'brand': brand,
                        'description': description,
                        'category': category,
                        'is_active': is_active,
                    }
                )
                created += 1
            else:
                errors.append(row)
        if errors:
            messages.warning(request, f"Some rows were skipped due to missing required fields or invalid category: {errors}")
            return redirect(manage_product_view)
        messages.success(request, f"{created} products added successfully.")
        return redirect(manage_product_view)
    return render(request, 'products/bulk_add_products.html')

@login_required
def download_product_template_view(request):
    """
    Provides a CSV template for bulk product upload.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="product_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['name', 'brand', 'description', 'category', 'is_active'])
    writer.writerow(['Example Product', 'BrandX', 'Description here', 'CategoryName', 'True'])
    return response

def product_autocomplete(request):
    q = request.GET.get('q', '')
    products = Product.objects.filter(name__icontains=q)[:20]
    results = [
        {'id': p.pk, 'text': p.name} for p in products
    ]
    return JsonResponse({'results': results})

@login_required
def bulk_add_product_unit_prices_view(request):
    """
    Bulk upload product unit prices via CSV.
    Expected CSV columns (case-insensitive):
      - product_sku OR product (sku or exact product name)
      - unit (unit of measure name)
      - conversion_factor (optional, defaults to 1.0)
      - price (required)

    Creates ProductUnitPrice records when product and unit are found. Skips rows with missing/invalid data.
    """
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)
        created, errors = 0, []
        for row in reader:
            # helper to fetch case-insensitive keys
            def get_row_val(keys):
                for k in keys:
                    val = row.get(k)
                    if val is not None:
                        return val.strip()
                return None

            product_key = get_row_val(['product_sku', 'sku', 'product'])
            unit_name = get_row_val(['unit', 'unit_name'])
            conv_raw = get_row_val(['conversion_factor', 'conversion'])
            price_raw = get_row_val(['price', 'unit_price'])

            # Resolve product
            product = None
            if product_key:
                product = Product.objects.filter(sku__iexact=product_key).first()
                if not product:
                    product = Product.objects.filter(name__iexact=product_key).first()

            # Resolve unit
            unit = None
            if unit_name:
                unit = UnitOfMeasure.objects.filter(name__iexact=unit_name).first()

            # Parse numeric values
            try:
                conversion_factor = float(conv_raw) if conv_raw not in (None, '') else 1.0
            except Exception:
                conversion_factor = 1.0

            try:
                price = int(float(price_raw)) if price_raw not in (None, '') else None
            except Exception:
                price = None
            
            if not product or not unit or price is None:
                errors.append({'row': row, 'reason': 'missing product/unit/price'})
                continue

            # Create or update ProductUnitPrice
            try:
                pup, created_flag = ProductUnitPrice.objects.update_or_create(
                    product=product,
                    unit=unit,
                    defaults={'conversion_factor': conversion_factor, 'price': price}
                )
                if created_flag:
                    created += 1
            except Exception as e:
                errors.append({'row': row, 'reason': str(e)})
                continue

        if errors:
            messages.warning(request, f"Some rows were skipped: {len(errors)}. See server logs for details.")
            messages.warning(request, errors)
        messages.success(request, f"Bulk upload finished — created/updated: {created}.")
        return redirect(manage_product_view)


@login_required
def download_product_unit_price_template_view(request):
    """Provide a CSV template for product unit prices bulk upload."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="product_unit_price_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['product_sku', 'unit', 'conversion_factor', 'price'])
    writer.writerow(['PRD-0001', 'Kilogram', '1.0', '3500'])
    return response

@login_required
def product_unit_prices_api(request, product_id):
    """Return JSON list of unit prices for a product.
    Response format: { results: [{unit_id, unit_name, price, conversion_factor}, ...] }
    """
    from django.shortcuts import get_object_or_404
    prod = get_object_or_404(Product, pk=product_id)
    unit_prices = prod.unit_prices.select_related('unit').all()
    results = []
    for up in unit_prices:
        results.append({
            'unit_id': up.unit.id,
            'unit_name': str(up.unit),
            'price': float(up.price),
            'conversion_factor': float(up.conversion_factor),
        })
    return JsonResponse({'results': results})







@login_required
def store_inventory_export_view(request, store_id):
    """
    Export store inventory to CSV format with InventoryBatch-based valuation.
    """
    
    store = get_object_or_404(StoreLocation, id=store_id)
    
    # Get all inventory (including zero stock for export)
    inventory_queryset = get_product_quantities_by_store(
        store_id=store_id, 
        include_zero_stock=True
    )
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = f"store_{store.name}_inventory_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Product Name',
        'SKU',
        'Brand',
        'Category',
        'Current Stock',
        'Reorder Level',
        'Average Unit Cost',
        'Total Value',
        'Batch Count',
        'Status'
    ])
    
    # Write data with InventoryBatch-based calculations
    for item in inventory_queryset:
        # Get detailed inventory value from batches
        product_value_data = get_product_inventory_value_by_store(
            store_id=store_id, 
            product_id=item.product.id
        )
        
        average_cost = product_value_data['average_cost']
        total_value = product_value_data['total_value']
        batch_count = product_value_data['batch_count']
        
        if item.quantity_in_stock == 0:
            status = 'Out of Stock'
        elif item.quantity_in_stock <= (item.reorder_level or 0):
            status = 'Low Stock'
        else:
            status = 'In Stock'
        
        writer.writerow([
            item.product.name,
            item.product.sku,
            item.product.brand or '',
            item.product.category.name if item.product.category else '',
            item.quantity_in_stock,
            item.reorder_level or '',
            f"{average_cost:.2f}",
            f"{total_value:.2f}",
            batch_count,
            status
        ])
    
    return response


@login_required
def store_inventory_view(request, store_id):
    """
    Display inventory/product quantities for a specific store.
    """
    
    store = get_object_or_404(StoreLocation, id=store_id)
    
    # Get query parameters
    search_query = request.GET.get('search', '').strip()
    show_zero_stock = request.GET.get('show_zero_stock', 'false').lower() == 'true'
    category_filter = request.GET.get('category', '')
    sort_by = request.GET.get('sort', 'product__name')
    
    # Get base inventory queryset
    inventory_queryset = Inventory.objects.filter(store_id=store_id).select_related('product', 'product__category')
    
    # Apply zero stock filter
    if not show_zero_stock:
        inventory_queryset = inventory_queryset.filter(quantity_in_stock__gt=0)
    
    # Apply search filter
    if search_query:
        inventory_queryset = inventory_queryset.filter(
            Q(product__name__icontains=search_query) |
            Q(product__sku__icontains=search_query) |
            Q(product__brand__icontains=search_query)
        )
    
    # Apply category filter
    if category_filter:
        inventory_queryset = inventory_queryset.filter(
            product__category_id=category_filter
        )
    
    # Apply sorting
    valid_sort_fields = [
        'product__name', '-product__name',
        'quantity_in_stock', '-quantity_in_stock',
        'reorder_level', '-reorder_level',
        'product__category__name', '-product__category__name'
    ]
    if sort_by in valid_sort_fields:
        inventory_queryset = inventory_queryset.order_by(sort_by)
    else:
        inventory_queryset = inventory_queryset.order_by('product__name')
    
    # Get categories for filter dropdown
    categories = Category.objects.filter(
        products__inventories__store_id=store_id
    ).distinct().order_by('name')
    
    # Pagination
    paginator = Paginator(inventory_queryset, 25)
    page_number = request.GET.get('page')
    inventory_page = paginator.get_page(page_number)
    
    # USE THE UPDATED OPTIMIZED FUNCTION
    inventory_summary = get_store_inventory_summary_optimized(store_id)
    
    context = {
        'store': store,
        'inventory_page': inventory_page,
        'inventory_summary': inventory_summary,
        'categories': categories,
        'search_query': search_query,
        'show_zero_stock': show_zero_stock,
        'category_filter': category_filter,
        'sort_by': sort_by,
        'total_items': paginator.count,
    }
    
    return render(request, 'products/store_inventory.html', context)


@login_required
def all_stores_inventory_view(request):
    """
    Overview of inventory across all stores with InventoryBatch-based calculations.
    Useful for managers to see stock levels across locations.
    """
   
    stores = StoreLocation.objects.all().order_by('name')
    stores_data = []
    
    for store in stores:
        summary = get_store_inventory_summary_optimized(store.id)
        summary['store'] = store
        stores_data.append(summary)
    
    # Calculate totals across all stores
    total_products = sum(data['total_products'] for data in stores_data)
    total_low_stock = sum(data['low_stock_count'] for data in stores_data)
    total_out_of_stock = sum(data['out_of_stock_count'] for data in stores_data)
    total_value = sum(data['total_inventory_value'] for data in stores_data)
    
    context = {
        'stores_data': stores_data,
        'totals': {
            'total_products': total_products,
            'total_low_stock': total_low_stock,
            'total_out_of_stock': total_out_of_stock,
            'total_value': total_value,
        }
    }
    
    return render(request, 'products/all_stores_inventory.html', context)





@login_required
def product_inventory_detail_view(request, store_id, product_id):
    """
    Detailed view of a specific product's inventory in a store.
    Shows batch-level details and valuation breakdown.
    """
    
    store = get_object_or_404(StoreLocation, id=store_id)
    product = get_object_or_404(Product, id=product_id)
    
    # Get detailed inventory information
    inventory_data = get_product_inventory_value_by_store(store_id, product_id)
    
    context = {
        'store': store,
        'product': product,
        'inventory_data': inventory_data,
    }
    
    return render(request, 'products/product_inventory_detail.html', context)


@login_required
def store_inventory_aging_report_view(request, store_id):
    """
    Show aging inventory report for a specific store.
    Helps identify slow-moving stock that may need attention.
    """
    
    store = get_object_or_404(StoreLocation, id=store_id)
    
    # Get aging threshold from query parameter (default 90 days)
    aging_days = int(request.GET.get('days', 90))
    
    # Get aging inventory
    aging_batches = get_inventory_aging_report(store_id, aging_days)
    
    # Pagination
    paginator = Paginator(aging_batches, 25)
    page_number = request.GET.get('page')
    aging_page = paginator.get_page(page_number)
    
    # Calculate totals
    total_aging_value = sum([
        batch.quantity_remaining * batch.unit_cost 
        for batch in aging_batches
    ])
    
    context = {
        'store': store,
        'aging_page': aging_page,
        'aging_days': aging_days,
        'total_aging_value': total_aging_value,
        'total_aging_items': paginator.count,
    }
    
    return render(request, 'products/store_inventory_aging.html', context)


@login_required 
def store_inventory_batch_api(request, store_id, product_id):
    """
    API endpoint to get batch details for a specific product in a store.
    Returns JSON data with batch information for inventory management.
    """
    
    store = get_object_or_404(StoreLocation, id=store_id)
    product = get_object_or_404(Product, id=product_id)
    
    inventory_data = get_product_inventory_value_by_store(store_id, product_id)
    
    return JsonResponse({
        'store_id': store_id,
        'store_name': store.name,
        'product_id': product_id,
        'product_name': product.name,
        'total_quantity': inventory_data['quantity_in_stock'],
        'total_value': inventory_data['total_value'],
        'average_cost': inventory_data['average_cost'],
        'batch_count': inventory_data['batch_count'],
        'batches': inventory_data['batches']
    })


@login_required
def store_low_stock_api(request, store_id):
    """
    Enhanced API endpoint to get low stock products for a specific store.
    Now includes batch-based valuation data.
    """
    
    store = get_object_or_404(StoreLocation, id=store_id)
    limit = int(request.GET.get('limit', 10))
    include_values = request.GET.get('include_values', 'false').lower() == 'true'
    
    # Get low stock products for this store
    low_stock_items = get_low_stock_products(limit=limit).filter(store_id=store_id)
    
    results = []
    for item in low_stock_items:
        result_data = {
            'product_id': item.product.id,
            'product_name': item.product.name,
            'sku': item.product.sku,
            'current_stock': item.quantity_in_stock,
            'reorder_level': item.reorder_level or 0,
            'category': item.product.category.name if item.product.category else '',
            'status': 'out_of_stock' if item.quantity_in_stock == 0 else 'low_stock'
        }
        
        # Include valuation data if requested
        if include_values:
            value_data = get_product_inventory_value_by_store(store_id, item.product.id)
            result_data.update({
                'total_value': value_data['total_value'],
                'average_cost': value_data['average_cost'],
                'batch_count': value_data['batch_count']
            })
        
        results.append(result_data)
    
    return JsonResponse({
        'store_id': store_id,
        'store_name': store.name,
        'low_stock_count': len(results),
        'results': results
    })


@login_required
def products_api(request):
    """
    API endpoint to get products with their basic information.
    Now includes real-time available stock calculations.
    """
    # Get query parameters
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category')
    active_only = request.GET.get('active_only', 'true').lower() == 'true'
    limit = int(request.GET.get('limit', 10000))
    store_id = request.GET.get('store_id')
    
    # Base queryset
    products = Product.objects.select_related('category')
    
    # Apply filters
    if active_only:
        products = products.filter(is_active=True)
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Apply search filter
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Order and limit
    products = products.order_by('name')[:limit]
    
    # Build response data with real-time stock
    results = []
    for product in products:
        product_data = {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'brand': product.brand or '',
            'description': product.description or '',
            'category': product.category.name if product.category else '',
            'category_id': product.category.id if product.category else None,
            'is_active': product.is_active,
        }
        
        # Add real-time stock information if store_id is provided
        if store_id:
            try:
                inventory = Inventory.objects.get(
                    product=product,
                    store_id=store_id
                )
                
                # Calculate committed stock for real-time availability
                committed_stock = StockTransferItem.objects.filter(
                    product=product,
                    stock_transfer__from_store_id=store_id,
                    stock_transfer__status__in=['pending', 'in_transit']
                ).aggregate(committed=Sum('quantity'))['committed'] or 0
                
                available_stock = max(0, inventory.quantity_in_stock - committed_stock)
                
                product_data.update({
                    'physical_stock': inventory.quantity_in_stock,
                    'committed_stock': committed_stock,
                    'available_stock': available_stock,
                    'reorder_level': inventory.reorder_level or 0,
                    'stock_status': 'out_of_stock' if available_stock == 0 else 
                                   'low_stock' if available_stock <= (inventory.reorder_level or 0) else 
                                   'in_stock'
                })
            except Inventory.DoesNotExist:
                product_data.update({
                    'physical_stock': 0,
                    'committed_stock': 0,
                    'available_stock': 0,
                    'reorder_level': 0,
                    'stock_status': 'not_tracked'
                })
        
        # Add unit prices if available
        unit_prices = []
        for unit_price in product.unit_prices.select_related('unit').all():
            unit_prices.append({
                'unit_id': unit_price.unit.id,
                'unit_name': str(unit_price.unit),
                'price': float(unit_price.price),
                'conversion_factor': float(unit_price.conversion_factor),
            })
        
        if unit_prices:
            product_data['unit_prices'] = unit_prices
        
        results.append(product_data)
    
    # Response metadata
    response_data = {
        'success': True,
        'count': len(results),
        'total_available': Product.objects.filter(is_active=True).count() if active_only else Product.objects.count(),
        'filters_applied': {
            'search': search_query,
            'category_id': category_id,
            'active_only': active_only,
            'store_id': store_id,
        },
        'products': results
    }
    
    return JsonResponse(response_data)



@login_required
def products_search_api(request):
    """
    Simplified product search API for autocomplete/select2 widgets.
    Returns minimal product info for dropdown population.
    """
    
    search_query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 20))
    
    if not search_query:
        return JsonResponse({'results': []})
    
    # Search products
    products = Product.objects.filter(
        Q(name__icontains=search_query) |
        Q(sku__icontains=search_query) |
        Q(brand__icontains=search_query),
        is_active=True
    ).order_by('name')[:limit]
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'text': f"{product.name} ({product.sku})",
            'name': product.name,
            'sku': product.sku,
            'brand': product.brand or '',
            'cost_price': float(product.cost_price or 0),
        })
    
    return JsonResponse({'results': results})


@login_required
def product_stock_api(request, product_id):
    """
    Get stock levels for a specific product across all stores or a specific store.
    Enhanced with real-time available stock calculations.
    """
    product = get_object_or_404(Product, id=product_id)
    store_id = request.GET.get('store_id')

    if store_id:
        # Get stock for specific store with real-time calculations
        try:
            inventory = Inventory.objects.get(
                product=product,
                store_id=store_id
            )
            
            # Calculate committed stock for real-time availability
            committed_stock = StockTransferItem.objects.filter(
                product=product,
                stock_transfer__from_store_id=store_id,
                stock_transfer__status__in=['pending', 'in_transit']
            ).aggregate(committed=Sum('quantity'))['committed'] or 0
            
            available_stock = max(0, inventory.quantity_in_stock - committed_stock)
            
            stock_data = {
                'store_id': int(store_id),
                'store_name': inventory.store.name,
                'physical_stock': inventory.quantity_in_stock,
                'committed_stock': committed_stock,
                'available_stock': available_stock,
                'reorder_level': inventory.reorder_level or 0,
            }
            
            # Add stock status based on available stock
            if available_stock == 0:
                stock_data['status'] = 'out_of_stock'
            elif available_stock <= (inventory.reorder_level or 0):
                stock_data['status'] = 'low_stock'
            else:
                stock_data['status'] = 'in_stock'
            
        except Inventory.DoesNotExist:
            stock_data = {
                'store_id': int(store_id),
                'physical_stock': 0,
                'committed_stock': 0,
                'available_stock': 0,
                'status': 'not_tracked',
                'error': 'Product not tracked in this store'
            }
    
    else:
        # Get stock across all stores with real-time calculations
        inventories = Inventory.objects.filter(product=product).select_related('store')
        
        stores_data = []
        total_physical = 0
        total_committed = 0
        total_available = 0
        
        for inventory in inventories:
            # Calculate committed stock for each store
            committed_stock = StockTransferItem.objects.filter(
                product=product,
                stock_transfer__from_store=inventory.store,
                stock_transfer__status__in=['pending', 'in_transit']
            ).aggregate(committed=Sum('quantity'))['committed'] or 0
            
            available_stock = max(0, inventory.quantity_in_stock - committed_stock)
            
            store_stock = {
                'store_id': inventory.store.id,
                'store_name': inventory.store.name,
                'physical_stock': inventory.quantity_in_stock,
                'committed_stock': committed_stock,
                'available_stock': available_stock,
                'reorder_level': inventory.reorder_level or 0,
            }
            
            if available_stock == 0:
                store_stock['status'] = 'out_of_stock'
            elif available_stock <= (inventory.reorder_level or 0):
                store_stock['status'] = 'low_stock'
            else:
                store_stock['status'] = 'in_stock'
            
            stores_data.append(store_stock)
            total_physical += inventory.quantity_in_stock
            total_committed += committed_stock
            total_available += available_stock
        
        stock_data = {
            'total_physical_stock': total_physical,
            'total_committed_stock': total_committed,
            'total_available_stock': total_available,
            'stores': stores_data
        }
    
    response_data = {
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'default_price': float(product.default_price or 0),
        },
        'stock': stock_data
    }
    
    return JsonResponse(response_data)



@login_required
def products_by_category_api(request, category_id):
    """
    Get all products in a specific category.
    Useful for filtering products by category in forms.
    """
    
    category = get_object_or_404(Category, id=category_id)
    active_only = request.GET.get('active_only', 'true').lower() == 'true'
    
    products = Product.objects.filter(category=category)
    if active_only:
        products = products.filter(is_active=True)
    
    products = products.order_by('name')
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'brand': product.brand or '',
            'cost_price': float(product.cost_price or 0),
            'selling_price': float(product.selling_price or 0),
            'unit': product.unit or 'Piece',
        })
    
    return JsonResponse({
        'success': True,
        'category': {
            'id': category.id,
            'name': category.name,
        },
        'products': results,
        'count': len(results)
    })


@login_required
def product_suggestions_api(request):
    """
    Get product suggestions based on various criteria.
    Useful for recommendation systems or quick access.
    """
    
    suggestion_type = request.GET.get('type', 'recent')
    limit = int(request.GET.get('limit', 10))
    store_id = request.GET.get('store_id')
    
    if suggestion_type == 'low_stock' and store_id:
        # Products with low stock in specific store
        products = Product.objects.filter(
            inventories__store_id=store_id,
            inventories__quantity_in_stock__lte=models.F('inventories__reorder_level'),
            is_active=True
        ).distinct().order_by('name')[:limit]
        
    elif suggestion_type == 'popular':
        # Most frequently used products (you might track this in stock movements)
        products = Product.objects.filter(
            is_active=True
        ).order_by('-created_at')[:limit]  # Placeholder - implement based on usage tracking
        
    elif suggestion_type == 'recent':
        # Recently added products
        products = Product.objects.filter(
            is_active=True
        ).order_by('-created_at')[:limit]
        
    else:
        # Default to alphabetical
        products = Product.objects.filter(
            is_active=True
        ).order_by('name')[:limit]
    
    results = []
    for product in products:
        product_data = {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'brand': product.brand or '',
            'category': product.category.name if product.category else '',
            'cost_price': float(product.cost_price or 0),
            'unit': product.unit or 'Piece',
        }
        
        # Add stock info if store specified
        if store_id:
            try:
                from app.models.products import Inventory
                inventory = Inventory.objects.get(
                    product=product,
                    store_id=store_id
                )
                product_data['available_stock'] = inventory.quantity_in_stock
            except Inventory.DoesNotExist:
                product_data['available_stock'] = 0
        
        results.append(product_data)
    
    return JsonResponse({
        'success': True,
        'suggestion_type': suggestion_type,
        'products': results,
        'count': len(results)
    })
    

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
