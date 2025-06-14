from django.shortcuts import render, redirect

from app.forms.product_forms import ProductForm, CategoryForm, UnitOfMeasureForm, ProductUnitPriceForm, InventoryForm, StoreLocationForm
from app.selectors.product_selectors import get_all_products, get_product_by_id, get_category_by_id, get_all_categories, get_all_units_of_measurement
from app.models.products import ProductUnitPrice, StoreLocation, Inventory



# manage products
def manage_product_view(request):
    product_form = ProductForm()

    products = get_all_products()
    categories = get_all_categories() #categories and products are viewed on the same html page

    context = {
        'form': product_form,
        'products': products,
        'categories': categories
    }
    return render(request, 'products.html', context)

def add_product_view(request):
    if request.method == 'POST':
       form = ProductForm(request.POST)

       if form.is_valid():
           form.save()
           return redirect(manage_product_view)
       
    else:
        form = ProductForm()

    context = {
        'form':form
    }

    return render(request, 'add_product.html', context)

def edit_product_view(request, product_id):

    product = get_product_by_id(product_id)

    if request.method == "POST":
        edit_form = ProductForm(request.POST, instance = product)
        
        if edit_form.is_valid():
            edit_form.save()
            return redirect(manage_product_view)
    else:
        edit_form = ProductForm(instance = product)

    context = {
        'edit_form':edit_form
    }
    return render(request, 'edit_product.html', context)

def add_category_view(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect(manage_product_view)
    else:
        form = CategoryForm()

    context = {
        'form':form
    }

    return render(request, 'add_category.html', context)

def category_view(request):
    return render(request, 'category.html')

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
    
    return render(request, 'unit_of_measure.html', context)

def product_details_view(request, _product_id):
    if request.method == "POST":
        form = ProductUnitPriceForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = ProductUnitPriceForm()

    item = get_product_by_id(_product_id)
    item_details = ProductUnitPrice.objects.get(product_id = item.id) #I still dont understand how the unit was fetched from the UnitOfMeasure model
        
    context = {
        'form':form,
        'item_details':item_details    
    }
    return render(request, 'product_details.html', context)

def inventory_view(request):
    if request.method == 'POST':
        form = InventoryForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = InventoryForm()
    
    product_details = []
    for item_id in Inventory.objects.values_list('store_id', flat = True):
        store_detail  = StoreLocation.objects.get(id = item_id)
        product = Inventory.objects.get(id = store_detail.id)
        product_details.append(product)
    

    context = {
        'form':form,
        'product_details':product_details,
    }
    return render(request, 'inventory.html', context)

def store_list_view(request):
    if request.method == "POST":
        form = StoreLocationForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = StoreLocationForm()

    context = {
        'form':form,
        
    }
    return render(request, 'store_list.html', context)

def add_store_view(request):
    return render(request, 'add_store.html')