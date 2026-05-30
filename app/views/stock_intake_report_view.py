from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from app.models.transactions import PurchaseOrderItem


@login_required
def stock_intake_report(request):
    """
    View to display a report of all stock intake (purchase order items).
    Matches Expenses Report layout with an Actual Stock column.
    """
    items = PurchaseOrderItem.objects.select_related(
        'order', 'order__supplier', 'order__store', 'product', 'unit'
    ).all().order_by('-order__purchase_date')

    total_cost = items.aggregate(total=Sum(F('unit_cost') * F('quantity')))['total'] or 0

    return render(request, 'stock_intake_report.html', {
        'items': items,
        'total_cost': total_cost,
    })
