from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from app.forms.transaction_forms import SalesForm, SalesItemFormSet
from app.selectors.sales_selectors import get_all_sales, get_sale_by_id, get_sales_items_for_sale
from app.models.transactions import Sales, SalesItem

@login_required
def sales_list_view(request):
    sales = get_all_sales()

    context = {
        'sales': sales,
    }

    return render(request, 'sales/sales_list.html', context)

@login_required
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
    else:
        form = SalesForm()
        formset = SalesItemFormSet(queryset=SalesItem.objects.none())
    
    context = {
        'form': form,
        'formset': formset,
    }
    
    return render(request, 'sales/record_sales.html', context)

@login_required
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

@login_required
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
    else:
        form = SalesForm(instance=sale)
        formset = SalesItemFormSet(queryset=get_sales_items_for_sale(sale))
    
    context = {
        'form': form,
        'formset': formset,
        'sale': sale,
    }
    return render(request, 'sales/sales_form.html', context)

@login_required
def sales_delete_view(request, pk):
    sale = get_object_or_404(Sales, pk=pk)
   
    sale.delete()
    messages.success(request, 'Sale deleted successfully.')
        
    return redirect(sales_list_view)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from app.forms.transaction_forms import SalesForm, SalesItemFormSet
from app.selectors.sales_selectors import get_all_sales, get_sale_by_id, get_sales_items_for_sale
from app.models.transactions import Sales, SalesItem


@login_required
def sales_list_view(request):
    sales = get_all_sales()
    return render(request, 'sales/sales_list.html', {'sales': sales})


@login_required
def sales_create_view(request):
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
            return redirect('sales_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SalesForm()
        formset = SalesItemFormSet(queryset=SalesItem.objects.none())
    return render(request, 'sales/sales_form.html', {'form': form, 'formset': formset})


@login_required
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
            return redirect('sales_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SalesForm(instance=sale)
        formset = SalesItemFormSet(queryset=get_sales_items_for_sale(sale))
    return render(request, 'sales/sales_form.html', {'form': form, 'formset': formset, 'sale': sale})

@login_required
def sales_detail_view(request, pk):
    sale = get_object_or_404(Sales, pk=pk)
    items = get_sales_items_for_sale(sale)
    return render(request, 'sales/sales_detail.html', {'sale': sale, 'items': items})

@login_required
def sales_delete_view(request, pk):
    sale = get_object_or_404(Sales, pk=pk)
    if request.method == 'POST':
        sale.delete()
        messages.success(request, 'Sale deleted successfully.')
        return redirect('sales_list')
    return render(request, 'sales/sales_confirm_delete.html', {'sale': sale})
