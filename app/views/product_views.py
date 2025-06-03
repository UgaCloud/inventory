from django.shortcuts import render, redirect

from app.forms.product_forms import ProductForm
from app.selectors.product_selectors import get_all_products, get_product_by_id
from app.selectors.category_selectors import get_all_categories
from app.models import Inventory



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

def delete_product_view(request, product_id):
    product = get_product_by_id(product_id)
    product.delete()
    return redirect(manage_product_view)

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