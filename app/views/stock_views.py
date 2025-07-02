from django.shortcuts import render, get_object_or_404, redirect, HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from app.models.transactions import StockMovement, StockTransfer, PurchaseOrder, PurchaseOrderItem
from app.forms.transaction_forms import StockMovementForm, StockTransferForm, PurchaseOrderForm, PurchaseOrderItemForm
from app.selectors.transaction_selectors import (
    get_all_stock_movements, get_stock_movement_by_id, get_stock_movements_by_branch,
    get_all_stock_transfers, get_stock_transfer_by_id, get_stock_transfers_by_branch,
    get_all_orders, get_order_by_id, get_orders_by_branch,
    get_items_by_order
)

def stock_dashboard(request):
    stock_movements = get_all_stock_movements()
    stock_transfers = get_all_stock_transfers()
    context = {
        'stock_movements': stock_movements,
        'stock_transfers': stock_transfers,
    }
    return render(request, 'stock_dashboard.html', context)

def stock_transfer_list(request):
    transfers = get_all_stock_transfers()
    return render(request, 'stock_transfer_list.html', {'transfers': transfers})

def stock_transfer_detail(request, transfer_id):
    transfer = get_stock_transfer_by_id(transfer_id)
    return render(request, 'stock_transfer_detail.html', {'transfer': transfer})

def create_stock_transfer(request):
    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Stock transfer recorded successfully.')
            return redirect('stock_transfer_list')
    else:
        form = StockTransferForm()
    return render(request, 'stock_transfer_form.html', {'form': form})

def edit_stock_transfer(request, transfer_id):
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    if request.method == 'POST':
        form = StockTransferForm(request.POST, instance=transfer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Stock transfer updated successfully.')
            return redirect('stock_transfer_list')
    else:
        form = StockTransferForm(instance=transfer)
    return render(request, 'stock_transfer_form.html', {'form': form, 'transfer': transfer})

def delete_stock_transfer(request, transfer_id):
    transfer = get_object_or_404(StockTransfer, id=transfer_id)
    if request.method == 'POST':
        transfer.delete()
        messages.success(request, 'Stock transfer deleted successfully.')
        return redirect('stock_transfer_list')
    return render(request, 'stock_transfer_confirm_delete.html', {'transfer': transfer})

def purchase_order_list(request):
    orders = get_all_orders()

    form = PurchaseOrderForm()

    context = {
        'purchase_orders': orders,
        'form': form,
    }
    return render(request, 'stock/purchase_order_list.html', context)

def purchase_order_detail(request, order_id):
    order = get_order_by_id(order_id)
    return render(request, 'purchase_order_detail.html', {'order': order})

def create_purchase_order(request):
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            order = form.save()
            messages.success(request, 'Purchase order created successfully.')
            
            return redirect(purchase_order_item_list, order_id = order.id)
    

def edit_purchase_order(request, order_id):
    order = get_object_or_404(PurchaseOrder, id=order_id)
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Purchase order updated successfully.')
            return redirect('purchase_order_list')
    else:
        form = PurchaseOrderForm(instance=order)
    return render(request, 'purchase_order_form.html', {'form': form, 'order': order})

def delete_purchase_order(request, order_id):
    order = get_object_or_404(PurchaseOrder, id=order_id)
    if request.method == 'POST':
        order.delete()
        messages.success(request, 'Purchase order deleted successfully.')
        return redirect('purchase_order_list')
    return render(request, 'purchase_order_confirm_delete.html', {'order': order})

def purchase_order_item_list(request, order_id):
    order = get_object_or_404(PurchaseOrder, id=order_id)
    items = get_items_by_order(order)
    
    form = PurchaseOrderItemForm(initial={'order': order})
    
    context = {
        'order': order, 
        'items': items,
        'form': form,
    }

    return render(request, 'stock/purchase_order_item_list.html', context)

def create_purchase_order_item(request, order_id):
    order = get_object_or_404(PurchaseOrder, id=order_id)
    
    if request.method == 'POST':
        form = PurchaseOrderItemForm(request.POST)
        
        if form.is_valid():
            item = form.save(commit=False)
            item.order = order
            item.save()
            
            messages.success(request, 'Purchase order item added successfully.')
            
        return redirect(purchase_order_item_list, order_id=order.id)
        

def edit_purchase_order_item(request, item_id):
    item = get_object_or_404(PurchaseOrderItem, id=item_id)
    order = item.order
    if request.method == 'POST':
        form = PurchaseOrderItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Purchase order item updated successfully.')
            return redirect('purchase_order_item_list', order_id=order.id)
    else:
        form = PurchaseOrderItemForm(instance=item)
    return render(request, 'purchase_order_item_form.html', {'form': form, 'order': order, 'item': item})

def delete_purchase_order_item(request, item_id):
    item = get_object_or_404(PurchaseOrderItem, id=item_id)
    order = item.order
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Purchase order item deleted successfully.')
        return redirect('purchase_order_item_list', order_id=order.id)
    return render(request, 'purchase_order_item_confirm_delete.html', {'item': item, 'order': order})
