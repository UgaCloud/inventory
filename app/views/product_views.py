from django.shortcuts import render

from app.forms.product_forms import ProductForm
from app.selectors.product_selectors import get_all_products

def manage_product_view(request):
    product_form = ProductForm()

    products = get_all_products()

    context = {
        'form': product_form,
        'products': products
    }
    return render(request, 'products/manage_products.html', context)