from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from app.models.expense import Expense


@login_required
def expenses_report(request):
    """
    View to display a report of all expenses.
    """
    expenses = Expense.objects.select_related(
        'store', 'category'
    ).all().order_by('-date')
    total = expenses.aggregate(total=Sum('amount'))['total'] or 0
    return render(request, 'expenses_report.html', {
        'expenses': expenses,
        'total': total,
    })
