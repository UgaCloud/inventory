from app.models.transactions import Sales, SalesItem
from django.db.models import Sum, F

def get_all_sales():
    """Return all sales, newest first."""
    return Sales.objects.all().order_by('-sale_date')

def get_sale_by_id(sale_id):
    """Return a single sale by its primary key."""
    return Sales.objects.filter(pk=sale_id).first()

def get_sales_for_customer(customer_id):
    """Return all sales for a given customer."""
    return Sales.objects.filter(customer_id=customer_id).order_by('-sale_date')

def get_sales_items_for_sale(sale):
    """Return all SalesItem objects for a given sale (can be instance or id)."""
    if isinstance(sale, int):
        return SalesItem.objects.filter(order_id=sale)
    return SalesItem.objects.filter(order=sale)

def get_total_sales_amount():
    """Return the total sales amount (sum of all sales' total_price)."""
    return Sales.objects.aggregate(total=Sum(F('items__quantity') * F('items__sale_price')))['total']

def get_total_items_sold():
    """Return the total number of items sold (sum of all SalesItem quantities)."""
    return SalesItem.objects.aggregate(total=Sum('quantity'))['total']

def get_sales_in_date_range(start_date, end_date):
    """Return all sales between two dates (inclusive)."""
    return Sales.objects.filter(sale_date__range=[start_date, end_date]).order_by('-sale_date')

def get_top_selling_products(limit=10):
    """Return the top N selling products by quantity sold."""
    return (
        SalesItem.objects.values('product__id', 'product__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:limit]
    )
