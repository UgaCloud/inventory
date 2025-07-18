from django.shortcuts import (
    render, redirect, 
    get_object_or_404, HttpResponseRedirect
)
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required

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
           messages.success(request, 'Product added successfully.')
       else:
           messages.error(request, 'There was an error adding the product.')
       return redirect(manage_product_view)
       

@login_required
def edit_product_view(request, product_id):
    product = get_product_by_id(product_id)
    if request.method == "POST":
        edit_form = ProductForm(request.POST, instance = product)
        if edit_form.is_valid():
            edit_form.save()
            messages.success(request, 'Product updated successfully.')
        else:
            messages.error(request, 'There was an error updating the product.')
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
            messages.success(request, 'Inventory added successfully.')
        else:
            messages.error(request, 'There was an error adding the inventory.')
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