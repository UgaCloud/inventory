from django.shortcuts import render, redirect

from app.forms.product_forms import ProductForm
from app.selectors.product_selectors import get_all_products
from app.selectors.category_selectors import get_all_categories


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

def delete_product_view(request, category_id):
    pass

def update_products_view(request):
    pass