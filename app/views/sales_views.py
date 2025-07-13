from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from app.forms.transaction_forms import SalesForm, SalesItemFormSet
from app.selectors.sales_selectors import get_all_sales, get_sale_by_id, get_sales_items_for_sale
from app.models.transactions import Sales, SalesItem


def sales_list_view(request):
    sales = get_all_sales()
    
    form = SalesForm()
    formset = SalesItemFormSet(queryset=SalesItem.objects.none())

    context = {
        'sales': sales,
        'form': form,
        'formset': formset,
    }

    return render(request, 'sales/sales_list.html', context)


def record_sales_view(request):
    if request.method == 'POST':
        form = SalesForm(request.POST)
        formset = SalesItemFormSet(request.POST, queryset=SalesItem.objects.none())
        
        if form.is_valid() and formset.is_valid():
            sale = form.save()
            sale_items = formset.save(commit=False)
            
            for item in sale_items:
                item.order = sale
                item.save()
            
            messages.success(request, 'Sale created successfully.')
            
            return redirect(sales_list_view)
        else:
            messages.error(request, 'Please correct the errors below.')

def sales_detail_view(request, pk):
    sale = get_object_or_404(Sales, pk=pk)
    items = get_sales_items_for_sale(sale)

    form = SalesForm(instance=sale)
    formset = SalesItemFormSet(queryset=get_sales_items_for_sale(sale))
    
    context = {
        'sale': sale,
        'items': items,
        'form': form,
        'formset': formset,
    }
    return render(request, 'sales/sales_detail.html', context)

def sales_update_view(request, pk):
    sale = get_object_or_404(Sales, pk=pk)
    
    if request.method == 'POST':
        form = SalesForm(request.POST, instance=sale)
        formset = SalesItemFormSet(request.POST, queryset=get_sales_items_for_sale(sale))
        
        if form.is_valid() and formset.is_valid():
            form.save()
            sale_items = formset.save(commit=False)
            
            for item in sale_items:
                item.order = sale
                item.save()
            
            for obj in formset.deleted_objects:
                obj.delete()
            
            messages.success(request, 'Sale updated successfully.')
            
            return redirect(sales_list_view)
        else:
            messages.error(request, 'Please correct the errors below.')

def sales_delete_view(request, pk):
    sale = get_object_or_404(Sales, pk=pk)
   
    sale.delete()
    messages.success(request, 'Sale deleted successfully.')
        
    return redirect(sales_list_view)
    
    return render(request, 'sales/sales_confirm_delete.html', {'sale': sale})
