from app.models.transactions import PurchaseOrder, Sales, StockTransfer, PurchaseOrderItem, SalesItem, StockMovement, StockAdjustment
from app.models.expense import Expense
from django.db.models import Sum, Count, F, Q
from datetime import date, timedelta

# PurchaseOrder selectors
def get_all_orders():
    return PurchaseOrder.objects.all()

def get_order_by_id(order_id):
    return PurchaseOrder.objects.filter(id=order_id).first()

def get_orders_by_branch(branch):
    return PurchaseOrder.objects.filter(branch=branch)

# PurchaseOrderItem selectors
def get_items_by_order(order):
    return PurchaseOrderItem.objects.filter(order=order)

# Sales selectors
def get_all_sales():
    return Sales.objects.all()

def get_sale_by_id(sale_id):
    return Sales.objects.filter(id=sale_id).first()

def get_sales_by_branch(branch):
    return Sales.objects.filter(branch=branch)

# SalesItem selectors
def get_items_by_sale(sale):
    return SalesItem.objects.filter(order=sale)

# StockTransfer selectors
def get_all_stock_transfers():
    return StockTransfer.objects.all()

def get_stock_transfer_by_id(transfer_id):
    return StockTransfer.objects.filter(id=transfer_id).first()

def get_stock_transfers_by_branch(branch):
    return StockTransfer.objects.filter(branch=branch)

# StockMovement selectors
def get_all_stock_movements():
    return StockMovement.objects.all()

def get_stock_movement_by_id(movement_id):
    return StockMovement.objects.filter(id=movement_id).first()

def get_stock_movements_by_branch(branch):
    return StockMovement.objects.filter(branch=branch)

def get_stock_movements_by_product(product):
    return StockMovement.objects.filter(product=product)

# PurchaseOrder advanced selectors
def get_orders_by_supplier(supplier):
    return PurchaseOrder.objects.filter(supplier=supplier)

def get_orders_by_status(status):
    return PurchaseOrder.objects.filter(status=status)

def get_orders_in_date_range(start_date, end_date):
    return PurchaseOrder.objects.filter(purchase_date__range=(start_date, end_date))

# Sales advanced selectors
def get_sales_by_customer(customer):
    return Sales.objects.filter(customer=customer)

def get_sales_by_status(status):
    return Sales.objects.filter(status=status)

def get_sales_in_date_range(start_date, end_date):
    return Sales.objects.filter(sale_date__range=(start_date, end_date))

# StockTransfer advanced selectors
def get_stock_transfers_by_product(product):
    return StockTransfer.objects.filter(product=product)

def get_stock_transfers_in_date_range(start_date, end_date):
    return StockTransfer.objects.filter(transfer_date__range=(start_date, end_date))

# StockMovement advanced selectors
def get_stock_movements_by_store(store):
    return StockMovement.objects.filter(store=store)

def get_stock_movements_in_date_range(start_date, end_date):
    return StockMovement.objects.filter(timestamp__date__range=(start_date, end_date))

# General utility selectors
def get_recent_orders(limit=10):
    return PurchaseOrder.objects.order_by('-purchase_date')[:limit]

def get_recent_sales(limit=5):
    
    return Sales.objects.order_by('-sale_date').prefetch_related('items', 'items__product', 'items__unit')[:limit]

def get_recent_stock_movements(limit=10):
    return StockMovement.objects.order_by('-timestamp')[:limit]

def get_total_purchases():
    today = date.today()
    result = PurchaseOrder.objects.filter(purchase_date=today).aggregate(total=Sum('total_cost'))
    return result['total'] or 0

def get_total_sales():
    today = date.today()
    result = Sales.objects.filter(sale_date=today).aggregate(total=Sum('total_amount'))
    return result['total'] or 0

def get_total_expenses():
    today = date.today()
    result = Expense.objects.filter(date=today).aggregate(total=Sum('amount'))
    return result['total'] or 0

def get_net_profit():
    total_sales = get_total_sales()
    total_expenses = get_total_expenses()
    total_purchases = get_total_purchases()
    return total_sales - total_purchases - total_expenses

def get_number_of_sales():
    return Sales.objects.count()

def get_todays_number_of_sales():
    today = date.today()
    result = Sales.objects.filter(sale_date=today).aggregate(count=Count('id'))
    return result['count'] or 0

def get_top_selling_products():
    
    return (
        SalesItem.objects.values('product__id', 'product__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:5]
    )

def get_total_payments_received():
    today = date.today()
    result = Sales.objects.filter(sale_date=today).aggregate(total=Sum('amount_received'))
    return result['total'] or 0

def get_total_outstanding_balances():
    result = Sales.objects.aggregate(total=Sum('balance'))
    return result['total'] or 0

def get_todays_outstanding_balances():
    today = date.today()
    result = Sales.objects.filter(sale_date=today).aggregate(total=Sum('balance'))
    return result['total'] or 0


def get_todays_collection_rate():
   
    today = date.today()
    
    # Get today's totals using aggregate to minimize database queries
    totals = Sales.objects.filter(sale_date=today).aggregate(
        total_sales=Sum('total_amount'),
        total_received=Sum('amount_received')
    )
    
    total_sales = totals['total_sales'] or 0
    total_received = totals['total_received'] or 0
    
    # Avoid division by zero
    if total_sales == 0:
        return 0
        
    collection_rate = (total_received / total_sales) * 100
    
    # Round to 2 decimal places
    return round(collection_rate, 2)

# ...existing code...

def get_todays_fully_paid_sales():
    """Get today's fully paid sales data"""
    today = date.today()
    
    fully_paid = Sales.objects.filter(
        sale_date=today,
        balance=0,
        total_amount=F('total_amount')
    ).aggregate(
        count=Count('id'),
        total_amount=Sum('total_amount'),
    )
    
    return {
        'count': fully_paid['count'] or 0,
        'total_amount': fully_paid['total_amount'] or 0,
    }

def get_todays_partially_paid_sales():
    """Get today's partially paid sales data"""
    today = date.today()
    
    partially_paid = Sales.objects.filter(
        sale_date=today,
        balance__gt=0,
        amount_received__gt=0
    ).aggregate(
        count=Count('id'),
        total_received=Sum('amount_received'),
    )
    
    return {
        'count': partially_paid['count'] or 0,
        'total_received': partially_paid['total_received'] or 0,
    }

def get_todays_unpaid_sales():
    """Get today's unpaid sales data"""
    today = date.today()

    unpaid = Sales.objects.filter(
        sale_date=today,
        amount_received=0
    ).aggregate(
        count=Count('id'),
        total_amount=Sum('total_amount')
    )
    
    return {
        'count': unpaid['count'] or 0,
        'total_amount': unpaid['total_amount'] or 0
    }

def get_todays_sales_summary():
    """Get complete summary of today's sales by payment status"""
    return {
        'fully_paid': get_todays_fully_paid_sales(),
        'partially_paid': get_todays_partially_paid_sales(),
        'unpaid': get_todays_unpaid_sales()
    }

# StockAdjustment selectors
def get_all_stock_adjustments():
    return StockAdjustment.objects.all().select_related('product', 'store', 'created_by').order_by('-created_at')

def get_recent_stock_adjustments(limit=10):
    return StockAdjustment.objects.select_related('product', 'store', 'created_by').order_by('-created_at')[:limit]

def get_pending_stock_adjustments():
    return StockAdjustment.objects.filter(status='pending').select_related('product', 'store', 'created_by').order_by('-created_at')

def get_todays_stock_adjustments():
    today = date.today()
    return StockAdjustment.objects.filter(created_at__date=today).select_related('product', 'store', 'created_by')

def get_stock_adjustments_count():
    return StockAdjustment.objects.count()

def get_pending_stock_adjustments_count():
    return StockAdjustment.objects.filter(status='pending').count()

def get_todays_stock_adjustments_count():
    today = date.today()
    return StockAdjustment.objects.filter(created_at__date=today).count()

def get_total_revenue():
    """Get total revenue (sales minus expenses)"""
    total_sales = Sales.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    total_expenses = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
    return total_sales - total_expenses