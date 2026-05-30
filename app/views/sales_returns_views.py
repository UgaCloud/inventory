from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from app.models.sales_return import SalesReturn

@login_required
def sales_returns_list_view(request):
    sales_returns = SalesReturn.objects.select_related('sale', 'sale__customer').order_by('-created_at')
    return render(request, 'sales/sales_returns.html', {'sales_returns': sales_returns})

@login_required
def sales_return_detail_view(request, pk):
    sales_return = get_object_or_404(SalesReturn, pk=pk)
    return render(request, 'sales/sales_return_detail.html', {'sales_return': sales_return})
