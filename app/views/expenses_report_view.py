from django.shortcuts import render
from app.models.expense import Expense  # Assuming Expense model exists


def expenses_report(request):
    """
    View to display a report of all expenses.
    """
    expenses = Expense.objects.all().order_by('-date')  # Adjust field names as needed
    total = sum(exp.amount for exp in expenses)
    return render(request, 'expenses_report.html', {
        'expenses': expenses,
        'total': total,
    })
