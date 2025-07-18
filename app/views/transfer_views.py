from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from app.models.transactions import TransferRequest, StockTransfer, StockTransferItem
from app.forms.transaction_forms import (
    TransferRequestForm, StockTransferForm, StockTransferItemForm, StockTransferItemFormSet, TransferRequestItemFormSet, 
    TransferRequestApprovalForm
)
from app.selectors.transfer_selectors import (
    get_all_transfer_requests, get_transfer_request_by_id, get_all_stock_transfers, get_stock_transfer_by_id
)

@login_required
def transfer_request_list(request):
    requests = get_all_transfer_requests()
    
    form = TransferRequestForm()
    formset = TransferRequestItemFormSet()
 
    context = {
        'requests': requests,
        'form': form,
        'item_formset': formset
    }
    
    return render(request, 'transfers/transfer_request_list.html', context)

@login_required
def add_transfer_request(request):
    
    if request.method == 'POST':
        form = TransferRequestForm(request.POST)
        formset = TransferRequestItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            transfer_request = form.save()
            formset.instance = transfer_request
            formset.save()
            
            messages.success(request, 'Transfer request created successfully.')
            
            return redirect(transfer_request_list)

@login_required
def transfer_request_detail(request, request_id):
    transfer_request = get_object_or_404(TransferRequest, pk=request_id)

    form = TransferRequestForm(instance=transfer_request)
    approval_form = TransferRequestApprovalForm(instance=transfer_request)
    request_items = transfer_request.items.all()

    context = {
        'request': transfer_request,
        'form': form, 
        'items':request_items,
        'approval_form': approval_form
    }

    return render(request, 'transfers/transfer_request_details.html', context)

@login_required
def update_transfer_request(request, request_id):
    
    transfer_request = get_object_or_404(TransferRequest, pk=request_id)
    
    if request.method == 'POST':
        form = TransferRequestForm(request.POST, instance=transfer_request)
        formset = TransferRequestItemFormSet(request.POST, instance=transfer_request)
       
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            messages.success(request, 'Transfer request updated successfully.')
            
            return redirect(transfer_request_list)

@login_required
def approve_transfer_request(request, request_id):
    transfer_request = get_object_or_404(TransferRequest, pk=request_id)
    
    if request.method == 'POST':
        form = TransferRequestApprovalForm(request.POST, instance=transfer_request)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Transfer request status updated successfully.')
            
            return redirect(transfer_request_detail, pk=request_id)
     

@login_required
def stock_transfer_list(request):
    transfers = get_all_stock_transfers()
    
    return render(request, 'transfers/stock_transfer_list.html', {'transfers': transfers})

@login_required
def stock_transfer_create(request):
    # Assume transfer_request_id is passed as GET or POST param
    transfer_request_id = request.GET.get('transfer_request_id') or request.POST.get('transfer_request')

    transfer_request = None
    initial_items = []

    if transfer_request_id:
        transfer_request = get_object_or_404(TransferRequest, id=transfer_request_id)
        
        # Get items from the transfer request
        initial_items = [
            {
                'product': item.product,
                'quantity': item.quantity,
                'transfer_request_item': item.id
            }
            for item in transfer_request.items.all()
        ]

    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        formset = StockTransferItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            transfer = form.save()
            formset.instance = transfer
            formset.save()
           
            messages.success(request, 'Stock transfer created successfully.')
            
            return redirect(stock_transfer_list)
    else:
        form = StockTransferForm(initial={'transfer_request': transfer_request_id} if transfer_request_id else None)
        
        formset = StockTransferItemFormSet(initial=initial_items)
    return render(request, 'stock_transfer_form.html', {'form': form, 'item_formset': formset, 'transfer_request': transfer_request})

@login_required
def stock_transfer_detail(request, pk):
    transfer_obj = get_stock_transfer_by_id(pk)
    if not transfer_obj:
        return render(request, '404.html', status=404)
    return render(request, 'stock_transfer_detail.html', {'transfer_obj': transfer_obj})

@login_required
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
