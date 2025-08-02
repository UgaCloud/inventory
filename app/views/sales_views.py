from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from app.forms.transaction_forms import SalesForm, SalesItemFormSet
from app.selectors.sales_selectors import get_all_sales, get_sale_by_id, get_sales_items_for_sale
from app.models.transactions import Sales, SalesItem
from app.services.customer_transactions import record_sale_and_payment

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
            sale_data = form.save(commit=False)
            
            # A call service to handle sale, payment, and ledger
            sale = record_sale_and_payment(
                customer=sale_data.customer,
                total_amount=sale_data.total_amount,
                amount_paid=sale_data.amount_paid,
                note=sale_data.note
            )
            
            sale.recorded_by = request.user.username
            sale.save()
            
            sale_items = formset.save(commit=False)
            for item in sale_items:
                item.order = sale
                item.save()
            messages.success(request, 'Sale created successfully.')
            return redirect(sales_list_view)
        else:
            # Collect and display all form and formset errors in messages
            error_list = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_list.append(f"{field}: {error}")
            for formset_form in formset:
                for field, errors in formset_form.errors.items():
                    for error in errors:
                        error_list.append(f"Item {formset_form.prefix} - {field}: {error}")
            if not error_list:
                error_list.append("Please correct the errors below.")
            for error in error_list:
                messages.error(request, error)
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
            sale = form.save(commit=False)
            # Set status based on balance
            if sale.balance > 0:
                sale.status = 'CREDIT'
            else:
                sale.status = 'PAID'
            # Set recorded_by to current user
            sale.recorded_by = request.user.username
            sale.save()
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

