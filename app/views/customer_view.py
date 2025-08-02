from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from app.models.customers import Customer, CustomerLedger, Payment
from app.forms.customer_forms import CustomerForm

@login_required
def customer_list_view(request):
    customers = Customer.objects.all()
    return render(request, 'customers/customer_list.html', {'customers': customers})

@login_required
def customer_detail_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    ledger_entries = customer.ledger_entries.order_by('-date')
    payments = customer.payments.order_by('-payment_date')
    return render(request, 'customers/customer_detail.html', {
        'customer': customer,
        'ledger_entries': ledger_entries,
        'payments': payments,
    })

@login_required
def customer_create_view(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Customer created successfully.')
            return redirect('customer_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomerForm()
    return render(request, 'customers/customer_form.html', {'form': form})

@login_required
def customer_update_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Customer updated successfully.')
            return redirect('customer_detail', pk=customer.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'customers/customer_form.html', {'form': form, 'customer': customer})

@login_required
def customer_delete_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.delete()
        messages.success(request, 'Customer deleted successfully.')
        return redirect('customer_list')
    return render(request, 'customers/customer_confirm_delete.html', {'customer': customer})
