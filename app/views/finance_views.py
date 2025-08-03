from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from app.models.finance import BankAccount, BankTransaction
from app.forms.finance_forms import BankAccountForm, BankTransactionForm
from app.selectors.finance_selectors import get_bank_accounts, get_bank_transactions, get_cashflows, get_cashflow_total
from app.models.products import StoreLocation
from app.constants import CASHFLOW_TYPES

# BankAccount Views

def bankaccount_list_view(request):
    accounts = get_bank_accounts(active_only=True)
    form = BankAccountForm()

    context = {
        'accounts': accounts,
        'form': form,
    }
    
    return render(request, 'finance/bankaccount_list.html', context)

def add_bankaccount_view(request):
    if request.method == 'POST':
        form = BankAccountForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bank account added successfully.')
            
        return redirect(bankaccount_list_view)


def update_bankaccount_view(request, pk):
    account = get_object_or_404(BankAccount, pk=pk)
    
    if request.method == 'POST':
        form = BankAccountForm(request.POST, instance=account)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Bank account updated successfully.')
            return redirect('bankaccount_list')
    else:
        form = BankAccountForm(instance=account)
    
    return render(request, 'finance/bankaccount_form.html', {'form': form, 'account': account})

def delete_bankaccount_view(request, pk):
    account = get_object_or_404(BankAccount, pk=pk)
    
    if request.method == 'POST':
        account.delete()
        messages.success(request, 'Bank account deleted successfully.')
        return redirect('bankaccount_list')
    
    return render(request, 'finance/bankaccount_confirm_delete.html', {'account': account})

# BankTransaction Views

def banktransaction_list_view(request):
    transactions = get_bank_transactions()
    form = BankTransactionForm()

    context = {
        'transactions': transactions,
        'form': form,
    }
    
    return render(request, 'finance/banktransaction_list.html', context)

def add_banktransaction_view(request):
    if request.method == 'POST':
        form = BankTransactionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bank transaction added successfully.')
            
        return redirect('banktransaction_list')

def update_banktransaction_view(request, pk):
    transaction = get_object_or_404(BankTransaction, pk=pk)
    if request.method == 'POST':
        form = BankTransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bank transaction updated successfully.')
            return redirect('banktransaction_list')
    else:
        form = BankTransactionForm(instance=transaction)
    return render(request, 'finance/banktransaction_form.html', {'form': form, 'transaction': transaction})

def delete_banktransaction_view(request, pk):
    transaction = get_object_or_404(BankTransaction, pk=pk)
    if request.method == 'POST':
        transaction.delete()
        messages.success(request, 'Bank transaction deleted successfully.')
        return redirect('banktransaction_list')
    return render(request, 'finance/banktransaction_confirm_delete.html', {'transaction': transaction})

# Cashflow Views

def cashflow_list_view(request):
    store = request.GET.get('store')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    transaction_type = request.GET.get('transaction_type')

    cashflows = get_cashflows(
        store=store or None,
        start_date=start_date or None,
        end_date=end_date or None,
        transaction_type=transaction_type or None
    )
    stores = StoreLocation.objects.filter(is_active=True)

    total_cashflow = None
    if cashflows.exists():
        total_cashflow = get_cashflow_total(
            store=store or None,
            start_date=start_date or None,
            end_date=end_date or None,
            transaction_type=transaction_type or None
        )
    context = {
        'cashflows': cashflows,
        'stores': stores,
        'cashflow_types': CASHFLOW_TYPES,
        'selected_store': store,
        'selected_start_date': start_date,
        'selected_end_date': end_date,
        'selected_transaction_type': transaction_type,
        'total_cashflow': total_cashflow,
    }
    return render(request, 'finance/cashflows.html', context)

