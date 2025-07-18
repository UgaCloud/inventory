from django.http import JsonResponse
from app.models.products import Product
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

@require_GET
@login_required
def product_autocomplete(request):
    term = request.GET.get('term', '')
    products = Product.objects.filter(name__icontains=term)[:10]
    results = [
        {'label': p.name, 'value': p.name, 'id': p.id}
        for p in products
    ]
    return JsonResponse(results, safe=False)
