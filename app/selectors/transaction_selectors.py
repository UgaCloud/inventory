from app.models.transactions import PurchaseOrder, Sales, StockTransfer

def get_all_orders():
    return PurchaseOrder.objects.all()
def get_all_sales():
    return Sales.objects.all()
def get_all_stock_transfers():
    return StockTransfer.objects.all()