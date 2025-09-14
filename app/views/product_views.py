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
from app.selectors.product_selectors import *
from app.models.products import *

from django.core.paginator import Paginator
from django.db.models import Q
import csv
from django.utils import timezone


@login_required
def manage_product_view(request):
    product_form = ProductForm()

    products = get_all_products()

    context = {
        'form': product_form,
        'products': products,
    }
    return render(request, 'products/products.html', context)

@login_required
def add_product_view(request):
    if request.method == 'POST':
       form = ProductForm(request.POST)

       if form.is_valid():
           form.save()
       
       return redirect(manage_product_view)
       
    

def edit_product_view(request, product_id):

    product = get_product_by_id(product_id)

    if request.method == "POST":
        edit_form = ProductForm(request.POST, instance = product)
        
        if edit_form.is_valid():
            edit_form.save()

        return redirect(product_details_view, product.id)

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
def product_details_view(request, _product_id):
    item = get_product_by_id(product_id=_product_id)

    product_form = ProductForm(instance=item)
    product_unit_price_form = ProductUnitPriceForm(initial={'product':item})
    inventory_form = InventoryForm(initial={'product': item})

    product_unit_prices = item.unit_prices.all()
    inventories = item.inventories.all()
    stock_movements = item.stock_movements.all()
        
    context = {
        'product_form': product_form,
        'product_unit_price_form': product_unit_price_form,
        'inventory_form': inventory_form,
        'product': item,
        'unit_prices':product_unit_prices,
        'inventories': inventories,
        'stock_movements': stock_movements,    
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
def store_inventory_view(request, store_id):
    """
    Display inventory/product quantities for a specific store.
    Includes filtering options and inventory summary with InventoryBatch-based calculations.
    """
    
    store = get_object_or_404(StoreLocation, id=store_id)
    
    # Get query parameters
    search_query = request.GET.get('search', '').strip()
    show_zero_stock = request.GET.get('show_zero_stock', 'false').lower() == 'true'
    category_filter = request.GET.get('category', '')
    sort_by = request.GET.get('sort', 'product__name')  # Default sort by product name
    
    # Get base inventory queryset
    inventory_queryset = get_product_quantities_by_store(
        store_id=store_id, 
        include_zero_stock=show_zero_stock
    )
    
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
    
    # Pagination
    paginator = Paginator(inventory_queryset, 25)  # Show 25 items per page
    page_number = request.GET.get('page')
    inventory_page = paginator.get_page(page_number)
    
    # Get store inventory summary using optimized InventoryBatch calculation
    inventory_summary = get_store_inventory_summary_optimized(store_id)
    
    # Get categories for filter dropdown
    categories = Category.objects.filter(
        products__inventories__store_id=store_id
    ).distinct().order_by('name')
    
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
