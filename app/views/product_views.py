from django.shortcuts import (
    render, redirect, 
    get_object_or_404, HttpResponseRedirect
)
from django.urls import reverse

from app.forms.product_forms import *
from app.selectors.product_selectors import *
from app.models.products import *


def manage_product_view(request):
    product_form = ProductForm()

    products = get_all_products()

    context = {
        'form': product_form,
        'products': products,
    }
    return render(request, 'products/products.html', context)

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

def add_category_view(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect(add_category_view)
    else:
        form = CategoryForm()
        categories = get_all_categories()

    context = {
        'form':form,
        'categories': categories
    }

    return render(request, 'products/add_category.html', context)

def delete_category_view(request, category_id):
    category = get_category_by_id(category_id)
    category.delete()
    return redirect(manage_product_view)

def unit_of_measure_view(request):

    if request.method == 'POST':
        form = UnitOfMeasureForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = UnitOfMeasureForm()

    units_of_measurement = get_all_units_of_measurement()
    
    context = {
        'form':form,
        'units_of_measurement':units_of_measurement
    }
    
    return render(request, 'products/unit_of_measure.html', context)

def product_details_view(request, _product_id):
    item = get_product_by_id(product_id=_product_id)

    product_form = ProductForm(instance=item)
    product_unit_price_form = ProductUnitPriceForm(initial={'product':item})
    inventory_form = InventoryForm(initial={'product': item})

    product_unit_prices = item.unit_prices.all()
    inventories = item.inventories.all()
        
    context = {
        'product_form': product_form,
        'product_unit_price_form': product_unit_price_form,
        'inventory_form': inventory_form,
        'product': item,
        'unit_prices':product_unit_prices,
        'inventories': inventories    
    }
    return render(request, 'products/product_details.html', context)

def add_product_unit_price_view(request):
    if request.method == 'POST':
        form = ProductUnitPriceForm(request.POST)
        if form.is_valid():
            form.save()
            
            return redirect(product_details_view, request.POST.get('product'))
    else:
        pass

def add_inventory_view(request):
    if request.method == 'POST':
        form = InventoryForm(request.POST)

        if form.is_valid():
            form.save()
  
    return redirect(product_details_view, request.POST.get('product'))

def store_view(request):
    if request.method == "POST":
        form = StoreLocationForm(request.POST)

        if form.is_valid():
            form.save()
    
    form = StoreLocationForm()
    stores = StoreLocation.objects.all()

    context = {
        'store_form':form,
        'stores': stores
        
    }
    return render(request, 'products/store.html', context)