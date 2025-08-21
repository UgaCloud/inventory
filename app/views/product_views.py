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
