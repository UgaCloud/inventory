from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from app.models.customers import Customer, CustomerLedger, Payment
from app.forms.customer_forms import CustomerForm
from app.forms.customer_forms import PaymentForm
from app.selectors.customer_selectors import *
from app.services.customer_transactions import allocate_bulk_payment_to_sales
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.urls import reverse
from app.forms.customer_forms import QuickCustomerForm
from app.models.tenancy import business_scope
from app.utils.list_helpers import list_context, panel_action

@login_required
def customer_list_view(request):
    customers = business_scope(request.user, Customer.objects.all())
    context = list_context(
        request,
        customers,
        search_fields=('name', 'email', 'phone', 'company', 'address'),
    )

    customers = context['page_obj'].object_list
    rows = []
    for customer in customers:
        balance = customer.balance or 0
        detail_url = reverse('customer_detail', args=[customer.pk])
        panel_id = f'app-panel-customer-{customer.pk}'
        rows.append({
            'icon': 'user',
            'category': 'customer',
            'title': customer.name,
            'meta': ' · '.join([part for part in [customer.email, customer.phone] if part]),
            'href': detail_url,
            'badges': (
                [{'label': 'Active', 'tone': 'success'}]
                if customer.is_active else [{'label': 'Inactive', 'tone': 'danger'}]
            ),
            'fields': [
                {'label': 'Company', 'value': customer.company or '—'},
                {'label': 'Balance', 'value': f'{balance:,.0f}'},
            ],
            'actions': [
                panel_action(panel_id),
                {'label': 'View customer', 'icon': 'eye', 'href': detail_url},
                {'label': 'Edit customer', 'icon': 'edit', 'href': f'#edit-modal-{customer.pk}'},
            ],
            'panel_id': panel_id,
            'panel': {
                'title': customer.name,
                'subtitle': customer.company or 'Customer record',
                'fields': [
                    {'label': 'Email', 'value': customer.email or '—'},
                    {'label': 'Phone', 'value': customer.phone or '—'},
                    {'label': 'Company', 'value': customer.company or '—'},
                    {'label': 'Balance', 'value': f'{balance:,.0f}'},
                    {'label': 'Status', 'value': 'Active' if customer.is_active else 'Inactive'},
                    {'label': 'Address', 'value': customer.address or '—'},
                ],
                'href': detail_url,
            },
        })

    context['rows'] = rows
    context['customers'] = customers
    context['search_placeholder'] = 'Search name, email, phone or company'
    context['toolbar_label'] = 'customers'
    return render(request, 'customers/customer_list.html', context)

@login_required
def customer_detail_view(request, pk):
    customer = get_object_or_404(business_scope(request.user, Customer.objects.all()), pk=pk)
    ledger_entries = customer.ledger_entries.order_by('-date')
    payments = customer.payments.order_by('-payment_date')

    form = CustomerForm(instance=customer)
    payment_form = PaymentForm(initial={'customer': customer})
    
    context = {
        'customer': customer,
        'ledger_entries': ledger_entries,
        'payments': payments,
        'form': form,
        'payment_form': payment_form,
    }
    return render(request, 'customers/customer_detail.html', context)

@login_required
def customer_create_view(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Customer created successfully.')
        else:
            messages.error(request, f'Please correct the errors below.\n{form.errors}')
    return redirect(customer_list_view)

@login_required
def customer_update_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)

        if form.is_valid():
            form.save()
            messages.success(request, 'Customer updated successfully.')
            return redirect('customer_detail', pk=customer.pk)
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

@login_required
def customer_ledger_list_view(request):
    """
    Lists all customer ledger entries for all customers.
    """
    ledger_entries = get_all_customer_ledgers()

    context = {
        'ledger_entries': ledger_entries,
    }
    
    return render(request, 'customers/customer_ledgers.html', context)

@login_required
def customer_ledger_detail_view(request, ledger_id):
    ledger_entry = get_object_or_404(CustomerLedger, pk=ledger_id)

    context = {
        'ledger_entry': ledger_entry,
        'customer': ledger_entry.customer,
    }
    
    return render(request, 'customers/customer_ledger_detail.html', context)

@login_required
def record_customer_payment_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment_amount = form.cleaned_data['amount']
            payment_method = form.cleaned_data['payment_method']
            reference = form.cleaned_data.get('reference', '')
            note = form.cleaned_data.get('note', '')

            allocate_bulk_payment_to_sales(
                customer=customer,
                payment_amount=payment_amount,
                payment_method=payment_method,
                reference=reference,
                note=note,
            )
            messages.success(request, 'Payment recorded and allocated to outstanding receipts.')
            return redirect('customer_detail', pk=customer.pk)
        messages.error(request, 'Please correct the errors below.')
    else:
        form = PaymentForm(initial={'customer': customer})

    return render(request, 'customers/payment_form.html', {'form': form, 'customer': customer})

@login_required
@require_POST
def create_customer_ajax(request):
    # Expect JSON body
    try:
        data = request.body.decode('utf-8')
        import json
        payload = json.loads(data) if data else {}
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    form = QuickCustomerForm(payload)
    if form.is_valid():
        customer = form.save()
        return JsonResponse({'id': customer.pk, 'name': str(customer)})
    else:
        # return form errors
        return JsonResponse(form.errors, status=400)

