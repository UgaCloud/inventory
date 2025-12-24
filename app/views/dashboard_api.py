from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from app.selectors.transaction_selectors import get_order_statistics, get_recent_sales
from django.views.decorators.http import require_GET

@login_required
def order_stats_api(request):
    period = request.GET.get('period', 'weekly')
    user = request.user
    if period == 'today':
        days = 1
    elif period == 'monthly':
        days = 30
    else:  # weekly default
        days = 7
    stats = get_order_statistics(days=days, user=user)
    return JsonResponse({'stats': stats})

@require_GET
@login_required
def recent_sales_api(request):
    user = request.user
    limit = int(request.GET.get('limit', 5))
    sales = get_recent_sales(user, limit=limit)
    sales_data = []
    for sale in sales:
        item = sale.items.first() if hasattr(sale, 'items') and sale.items.exists() else None
        sales_data.append({
            'id': sale.id,
            'product': str(item.product) if item else '',
            'category': str(item.product.category) if item and hasattr(item.product, 'category') else '',
            'amount': float(sale.total_amount),
            'date': sale.sale_date.strftime('%Y-%m-%d'),
            'status': sale.status,
            'img': item.product.image.url if item and hasattr(item.product, 'image') and item.product.image else '',
        })
    return JsonResponse({'sales': sales_data})
