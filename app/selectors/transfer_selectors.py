from app.models.transactions import StockTransfer, StockTransferItem, TransferRequest
from django.db.models import Sum, Q

def get_all_stock_transfers():
    return StockTransfer.objects.all()

def get_stock_transfer_by_id(transfer_id):
    return StockTransfer.objects.filter(id=transfer_id).first()

def get_stock_transfers_for_request(request_id):
    return StockTransfer.objects.filter(transfer_request_id=request_id)

def get_stock_transfer_items(transfer_id):
    return StockTransferItem.objects.filter(stock_transfer_id=transfer_id)

def get_total_quantity_transferred(product_id=None, from_date=None, to_date=None):
    qs = StockTransferItem.objects.all()
    if product_id:
        qs = qs.filter(product_id=product_id)
    if from_date:
        qs = qs.filter(stock_transfer__transfer_date__gte=from_date)
    if to_date:
        qs = qs.filter(stock_transfer__transfer_date__lte=to_date)
    return qs.aggregate(total=Sum('quantity'))['total'] or 0

def get_pending_transfer_requests():
    return TransferRequest.objects.filter(status='pending')

def get_fulfilled_transfer_requests():
    return TransferRequest.objects.filter(status='fulfilled')

def get_all_transfer_requests():
    return TransferRequest.objects.all()

def get_transfer_request_by_id(request_id):
    return TransferRequest.objects.filter(id=request_id).first()

def get_transfer_request_items(request_id):
    return StockTransferItem.objects.filter(stock_transfer__transfer_request_id=request_id)

def get_all_stock_transfer_items():
    return StockTransferItem.objects.all()

def get_stock_transfer_item_by_id(item_id):
    return StockTransferItem.objects.filter(id=item_id).first()
