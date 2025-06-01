from django.shortcuts import render

from app.forms.product_forms import ProductForm
from app.selectors.product_selectors import get_all_products
from app.models.products import Product

def manage_product_view(request):
    product_form = ProductForm()

    products = get_all_products()

    context = {
        'form': product_form,
        'products': products
    }
    return render(request, 'products.html', context)

def add_product_view(request):
    if request.method == 'POST':
        product_name = request.POST.get('name')
        sku = request.POST.get('sku')
        description = request.POST.get('name')
        barcode = request.POST.get('barcode')
        uuid_code = request.POST.get('uuid_code')
        category = request.POST.get('category')
        is_active = request.POST.get('is_active')
        created_at = request.POST.get('name')

        product = Product.objects.create(
            name = product_name,
            sku = sku,
            description = description,
            barcode = barcode,
            category = category,
            created_at = created_at
            )
        
        product.save()
    return render(request, 'add_product.html')

def update_products_view(request):
    pass