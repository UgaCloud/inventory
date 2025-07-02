from app.models.transactions import PurchaseOrder, Sales, StockTransfer, PurchaseOrderItem, SalesItem, StockMovement

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

def get_recent_sales(limit=10):
    return Sales.objects.order_by('-sale_date')[:limit]

def get_recent_stock_movements(limit=10):
    return StockMovement.objects.order_by('-timestamp')[:limit]