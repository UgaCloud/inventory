from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from app.models.products import Product, Automotive
from app.models.customers import Customer
from app.models.suppliers import Supplier


@login_required
def global_search_api(request):
    """
    API endpoint for system-wide search.
    Searches across products, customers, suppliers, and automotives.
    Returns JSON with categorized results.
    """
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    results = []
    limit = 5  # max results per category

    # Products
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(sku__icontains=query) |
        Q(brand__icontains=query) |
        Q(barcode__icontains=query)
    )[:limit]
    for p in products:
        results.append({
            'category': 'Products',
            'icon': 'ti-package',
            'title': p.name,
            'subtitle': f'SKU: {p.sku} | Brand: {p.brand or "-"}',
            'url': f'/product_details/{p.id}/',
        })

    # Customers
    customers = Customer.objects.filter(
        Q(name__icontains=query) |
        Q(email__icontains=query) |
        Q(phone__icontains=query) |
        Q(company__icontains=query)
    )[:limit]
    for c in customers:
        results.append({
            'category': 'Customers',
            'icon': 'ti-users',
            'title': c.name,
            'subtitle': f'{c.email or ""} | {c.phone or ""}',
            'url': f'/customers/{c.id}/',
        })

    # Suppliers
    suppliers = Supplier.objects.filter(
        Q(name__icontains=query) |
        Q(email__icontains=query) |
        Q(phone__icontains=query)
    )[:limit]
    for s in suppliers:
        results.append({
            'category': 'Suppliers',
            'icon': 'ti-truck',
            'title': s.name,
            'subtitle': f'{s.email or ""} | {s.phone or ""}',
            'url': f'/edit_supplier/{s.id}',
        })

    # Automotives
    automotives = Automotive.objects.filter(
        Q(brand__icontains=query) |
        Q(model__icontains=query) |
        Q(engine_type__icontains=query)
    )[:limit]
    for a in automotives:
        results.append({
            'category': 'Automotives',
            'icon': 'ti-car',
            'title': f'{a.brand} {a.model}',
            'subtitle': f'{a.year_from}-{a.year_to or "Present"} | {a.engine_type or "-"}',
            'url': f'/automotives/{a.id}/edit/',
        })

    return JsonResponse({'results': results})
