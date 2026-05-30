from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from app.models.customers import Customer, Payment
from app.models.transactions import Sales

@login_required
def customer_balance_report(request):
    # Annotate each customer with total sales and total payments
    customers = Customer.objects.all()
    customer_data = []
    for c in customers:
        total_sales = Sales.objects.filter(customer=c, is_cancelled=False).aggregate(total=Sum('total_amount'))['total'] or 0
        total_payments = Payment.objects.filter(customer=c).aggregate(total=Sum('amount'))['total'] or 0
        balance = total_sales - total_payments
        customer_data.append({
            'name': c.name,
            'email': c.email,
            'phone': c.phone,
            'company': c.company,
            'total_sales': total_sales,
            'total_payments': total_payments,
            'balance': balance,
        })
    return render(request, 'reports/customer_balance_report.html', {'customers': customer_data})
