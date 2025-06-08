from django.shortcuts import render
from app.forms.transaction_forms import PurchaseOrderForm, SalesForm, StockTransferForm

def purchase_order_view(request):
    if request.method == "POST":
        form = PurchaseOrderForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = PurchaseOrderForm()

    context = {
        'form':form
    }
    return render(request, 'purchase.html', context)

def sales_view(request):
    if request.method == "POST":
        form = SalesForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = SalesForm()

    context = {
        'form':form
    }
    return render(request, 'sales.html', context)

def stock_transfer_view(request):
    if request.method == "POST":
        form = StockTransferForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = StockTransferForm()

    context = {
        'form':form
    }
    return render(request, 'stock_transfer.html', context)