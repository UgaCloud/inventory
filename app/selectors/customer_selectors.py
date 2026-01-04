from django.db.models import Sum
from app.models.transactions import Sales

def get_top_customers(limit=5):
    """
    Returns a queryset of top customers by total sales amount, descending.
    Each result includes: customer, total_sales, total_orders, and country (if available).
    """
    return (
        Customer.objects.annotate(
            total_sales=Sum('sales__total_amount'),
            total_orders=Sum('sales__id')
        )
        .order_by('-total_sales')[:limit]
    )
from app.models.customers import Customer, CustomerLedger

def get_all_customers():
    return Customer.objects.all()

def get_number_of_customers():
    return Customer.objects.count()

def get_all_customer_ledgers():
    return CustomerLedger.objects.all()

def get_customer_ledger(ledger_id):
    return CustomerLedger.objects.filter(pk=ledger_id).first()

def get_ledgers_for_customer(customer):
    return CustomerLedger.objects.filter(customer=customer).order_by('-date')