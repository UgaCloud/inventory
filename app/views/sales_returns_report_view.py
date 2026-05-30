from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from app.models.sales_return import SalesReturn


@login_required
def sales_returns_report(request):
    """
    View to display a report of all sales returns.
    """
    sales_returns = SalesReturn.objects.select_related(
        'sale', 'sale__customer'
    ).all().order_by('-created_at')
    total = sales_returns.aggregate(total=Sum('amount'))['total'] or 0
    return render(request, 'sales_returns_report.html', {
        'sales_returns': sales_returns,
        'total': total,
    })
