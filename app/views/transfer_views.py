from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from app.models.transactions import TransferRequest, StockTransfer, StockTransferItem
from app.forms.transaction_forms import (
    TransferRequestForm, StockTransferForm, StockTransferItemForm, StockTransferItemFormSet
)
from app.selectors.transfer_selectors import (
    get_all_transfer_requests, get_transfer_request_by_id, get_all_stock_transfers, get_stock_transfer_by_id
)

def transfer_request_list(request):
    requests = get_all_transfer_requests()
    form = TransferRequestForm(request.POST)

    context = {
        'requests': requests,
        'form': form
    }
    return render(request, 'transfers/transfer_request_list.html', context)

def transfer_request_detail(request, pk):
    request_obj = get_object_or_404(TransferRequest, pk=pk)
    return render(request, 'transfer_request_detail.html', {'request_obj': request_obj})

def add_transfer_request(request):
    if request.method == 'POST':
        form = TransferRequestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transfer request created successfully.')

        return redirect(transfer_request_list)

def update_transfer_request(request, pk):
    transfer_request = get_object_or_404(TransferRequest, pk=pk)
    
    if request.method == 'POST':
        form = TransferRequestForm(request.POST, instance=transfer_request)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Transfer request updated successfully.')
            
        return redirect(transfer_request_list)

def stock_transfer_list(request):
    transfers = get_all_stock_transfers()
    return render(request, 'stock_transfer_list.html', {'transfers': transfers})

def stock_transfer_detail(request, pk):
    transfer_obj = get_stock_transfer_by_id(pk)
    if not transfer_obj:
        return render(request, '404.html', status=404)
    return render(request, 'stock_transfer_detail.html', {'transfer_obj': transfer_obj})

def stock_transfer_create(request):
    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        formset = StockTransferItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            transfer = form.save()
            formset.instance = transfer
            formset.save()
            messages.success(request, 'Stock transfer created successfully.')
            return redirect('stock_transfer_list')
    else:
        form = StockTransferForm()
        formset = StockTransferItemFormSet()
    return render(request, 'stock_transfer_form.html', {'form': form, 'item_formset': formset})

def stock_transfer_update(request, pk):
    transfer = get_object_or_404(StockTransfer, pk=pk)
    if request.method == 'POST':
        form = StockTransferForm(request.POST, instance=transfer)
        formset = StockTransferItemFormSet(request.POST, instance=transfer)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Stock transfer updated successfully.')
            return redirect('stock_transfer_list')
    else:
        form = StockTransferForm(instance=transfer)
        formset = StockTransferItemFormSet(instance=transfer)
    return render(request, 'stock_transfer_form.html', {'form': form, 'item_formset': formset})
