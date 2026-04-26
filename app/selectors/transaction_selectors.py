# ===========================
# ORDER STATISTICS (for dashboard)
# ===========================

from django.utils import timezone
from django.db import connection
from django.db.models.functions import TruncDate, Cast
from django.db.models import DateField
from datetime import timedelta



def get_order_statistics(days=7, user=None):
    today = timezone.now().date()
    start_date = today - timedelta(days=days-1)
    qs = Sales.objects.filter(
        sale_date__range=(start_date, today),
        is_cancelled=False  # Exclude cancelled sales
    )
    if user:
        qs = qs.filter(recorded_by=user)
    
    if connection.vendor == 'sqlite':
        # SQLite: Cast to Date
        stats = (
            qs.annotate(day=Cast('sale_date', output_field=DateField()))
            .values('day')
            .annotate(count=Count('id'), total=Sum('total_amount'))
            .order_by('day')
        )
    else:
        # Other DBs: Use TruncDate
        stats = (
            qs.annotate(day=TruncDate('sale_date'))
            .values('day')
            .annotate(count=Count('id'), total=Sum('total_amount'))
            .order_by('day')
        )
    
    # Fill missing days with zeroes
    result = []
    day_map = {s['day']: s for s in stats}
    for i in range(days):
        d = start_date + timedelta(days=i)
        entry = day_map.get(d, {'day': d, 'count': 0, 'total': 0})
        result.append({'date': d.strftime('%Y-%m-%d'), 'count': entry['count'], 'total': float(entry['total'] or 0)})
    return result



from django.db.models import Sum, Count, F
from datetime import date
from app.models.transactions import *
from app.models.expense import Expense


# ===========================
# SALES
# ===========================

def get_all_sales(user=None, is_cancelled=False):
    qs = Sales.objects.filter(is_cancelled=is_cancelled)
    if user:
        qs = qs.filter(recorded_by=user)
    return qs.order_by("-sale_date")


def get_sale_by_id(sale_id, user=None):
    qs = Sales.objects.filter(id=sale_id, is_cancelled=False)  
    if user:
        qs = qs.filter(recorded_by=user)
    return qs.first()


def get_sales_by_customer(customer, user=None):
    qs = Sales.objects.filter(customer=customer, is_cancelled=False)  
    if user:
        qs = qs.filter(recorded_by=user)
    return qs



def get_sales_in_date_range(start_date, end_date, user=None):
    qs = Sales.objects.filter(
        sale_date__range=(start_date, end_date), 
        is_cancelled=False  
    )
    if user:
        qs = qs.filter(recorded_by=user)
    return qs


def get_recent_sales(user=None, limit=5):
    qs = Sales.objects.filter(is_cancelled=False).order_by("-sale_date")  
    if user:
        qs = qs.filter(recorded_by=user)
    return qs[:limit]


def get_total_sales_per_user(user, date=None):
    """
    Returns total sales for a specific user on a specific day.
    User is required.
    """

    if date is None:
        date = timezone.now().date()

    total = (
        Sales.objects
        .filter(
            is_cancelled=False,
            recorded_by=user,
            sale_date=date
        )
        .aggregate(total=Sum("total_amount"))["total"]
    )

    return total or 0


def get_total_sales():
    return (
        Sales.objects
        .filter(is_cancelled=False)
        .aggregate(total=Sum("total_amount"))["total"] or 0
    )


def get_todays_number_of_sales(user=None):
    today = date.today()
    qs = Sales.objects.filter(sale_date=today, is_cancelled=False)  
    if user:
        qs = qs.filter(recorded_by=user)
    return qs.count()


def get_total_payments_received(user=None):
    today = date.today()
    qs = Sales.objects.filter(sale_date=today, is_cancelled=False) 
    if user:
        qs = qs.filter(recorded_by=user)
    return qs.aggregate(total=Sum("amount_received"))["total"] or 0


def get_todays_outstanding_balances(user=None):
    today = date.today()
    qs = Sales.objects.filter(sale_date=today, is_cancelled=False)  
    if user:
        qs = qs.filter(recorded_by=user)
    return qs.aggregate(total=Sum("balance"))["total"] or 0



def get_todays_fully_paid_sales(user=None):
    today = date.today()
    qs = Sales.objects.filter(
        sale_date=today, 
        balance=0, 
        is_cancelled=False  # Exclude cancelled
    )
    if user:
        qs = qs.filter(recorded_by=user)
    data = qs.aggregate(
        count=Count("id"),
        total_amount=Sum("total_amount"),
    )
    return {
        "count": data["count"] or 0,
        "total_amount": data["total_amount"] or 0,
    }


def get_todays_partially_paid_sales(user=None):
    today = date.today()
    qs = Sales.objects.filter(
        sale_date=today,
        balance__gt=0,
        amount_received__gt=0,
        is_cancelled=False  # Exclude cancelled
    )
    if user:
        qs = qs.filter(recorded_by=user)
    data = qs.aggregate(
        count=Count("id"),
        total_received=Sum("amount_received"),
    )
    return {
        "count": data["count"] or 0,
        "total_received": data["total_received"] or 0,
    }


def get_todays_collection_rate(user=None):
    today = date.today()
    qs = Sales.objects.filter(sale_date=today, is_cancelled=False)  # Exclude cancelled
    if user:
        qs = qs.filter(recorded_by=user)

    totals = qs.aggregate(
        total_sales=Sum("total_amount"),
        total_received=Sum("amount_received"),
    )

    if not totals["total_sales"]:
        return 0

    return round((totals["total_received"] / totals["total_sales"]) * 100, 2)


# ===========================
# SALES ITEMS / PRODUCTS
# ===========================

def get_items_by_sale(sale):
    return SalesItem.objects.filter(order=sale)


def get_top_selling_products(limit=5):
    return (
        SalesItem.objects.filter(
            order__is_cancelled=False  # Exclude items from cancelled sales
        )
        .values("product__id", "product__name")
        .annotate(total_sold=Sum("quantity"))
        .order_by("-total_sold")[:limit]
    )



# ===========================
# PURCHASES
# ===========================

def get_all_orders():
    return PurchaseOrder.objects.all()


def get_orders_by_branch(branch):
    return PurchaseOrder.objects.filter(branch=branch)


def get_orders_by_supplier(supplier):
    return PurchaseOrder.objects.filter(supplier=supplier)


def get_orders_in_date_range(start, end):
    return PurchaseOrder.objects.filter(purchase_date__range=(start, end))


def get_total_purchases():
    today = date.today()
    return (
        PurchaseOrder.objects.filter(purchase_date=today)
        .aggregate(total=Sum("total_cost"))["total"]
        or 0
    )


def get_order_by_id(order_id):
    return PurchaseOrder.objects.filter(id=order_id).first()


def get_items_by_order(order):
    return PurchaseOrderItem.objects.filter(order=order)


# ===========================
# STOCK
# ===========================

def get_all_stock_transfers():
    return StockTransfer.objects.all()


def get_stock_transfers_by_branch(branch):
    return StockTransfer.objects.filter(branch=branch)


def get_stock_movements_by_product(product):
    return StockMovement.objects.filter(product=product)


def get_stock_movements_by_store(store):
    return StockMovement.objects.filter(store=store)


def get_recent_stock_movements(limit=10):
    return StockMovement.objects.order_by("-timestamp")[:limit]


def get_all_stock_movements():
    return StockMovement.objects.all()


def get_stock_transfer_by_id(transfer_id):
    return StockTransfer.objects.filter(id=transfer_id).first()


# ===========================
# STOCK ADJUSTMENTS
# ===========================

def get_all_stock_adjustments():
    return StockAdjustment.objects.select_related(
        "product", "store", "created_by"
    ).order_by("-created_at")


def get_recent_stock_adjustments(limit=10):
    return StockAdjustment.objects.select_related(
        "product", "store", "created_by"
    ).order_by("-created_at")[:limit]


def get_pending_stock_adjustments():
    return StockAdjustment.objects.filter(status="pending")


def get_todays_stock_adjustments():
    today = date.today()
    return StockAdjustment.objects.filter(created_at__date=today)


def get_stock_adjustments_count():
    return StockAdjustment.objects.count()


def get_pending_stock_adjustments_count():
    return StockAdjustment.objects.filter(status="pending").count()


def get_total_revenue():
    total_sales = Sales.objects.filter(is_cancelled=False).aggregate(total=Sum("total_amount"))["total"] or 0
    total_expenses = Expense.objects.aggregate(total=Sum("amount"))["total"] or 0
    return total_sales - total_expenses

