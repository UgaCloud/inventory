from django.shortcuts import render
from app.forms.transaction_forms import PurchaseOrderForm, SalesForm, StockTransferForm
from app.selectors.transaction_selectors import get_all_orders, get_all_sales, get_all_stock_transfers

def purchase_order_view(request):
    if request.method == "POST":
        form = PurchaseOrderForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = PurchaseOrderForm()

    orders = get_all_orders()

    context = {
        'form':form,
        'orders':orders
    }
    return render(request, 'purchase_order.html', context)

def sales_view(request):
    if request.method == "POST":
        form = SalesForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = SalesForm()

    sales = get_all_sales()

    context = {
        'form':form,
        'sales':sales
    }
    return render(request, 'sales_list.html', context)

def stock_transfer_view(request):
    if request.method == "POST":
        form = StockTransferForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = StockTransferForm()

    stock_transfers = get_all_stock_transfers()

    context = {
        'form':form,
        'stock_transfers':stock_transfers
    }
    return render(request, 'stock_transfer.html', context)

#newly created
def pos_view(request):
    return render(request, 'pos.html')

def sales_return_view(request):
    return render(request, 'sales_return_list.html')

def create_sales_return_view(request):
    return render(request, 'create_sales_return.html')

def purchase_list_view(request):
    return render(request, 'purchase_list.html')

def add_purchase_view(request):
    return render(request, 'add_purchase.html')