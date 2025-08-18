from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from app.models.finance import BankAccount, BankTransaction, DailyCashSummary, CashFlow
from app.forms.finance_forms import BankAccountForm, BankTransactionForm
from app.selectors.finance_selectors import get_bank_accounts, get_bank_transactions, get_cashflows, get_cashflow_total
from app.models.products import StoreLocation
from app.constants import CASHFLOW_TYPES
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum

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
        'cashflow_types': CASHFLOW_TYPES,
        'selected_store': store,
        'selected_start_date': start_date,
        'selected_end_date': end_date,
        'selected_transaction_type': transaction_type,
        'total_cashflow': total_cashflow,
    }
    return render(request, 'finance/cashflows.html', context)

@require_POST
def close_day_view(request):
    store_id = request.POST.get('store_id')
    date_str = request.POST.get('date')
    if not store_id or not date_str:
        return JsonResponse({'success': False, 'error': 'Store and date are required.'}, status=400)
    try:
        store = StoreLocation.objects.get(id=store_id)
        date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    # Opening balance: closing balance of previous day, or 0 if none
    prev_summary = DailyCashSummary.objects.filter(store=store, date=date - timezone.timedelta(days=1)).first()
    opening_balance = prev_summary.closing_balance if prev_summary else 0
    # Sum all cash flows for the day
    cashflows = CashFlow.objects.filter(store=store, date=date)
    total_flow = cashflows.aggregate(total=Sum('amount'))['total'] or 0
    calculated_balance = opening_balance + total_flow
    closing_balance = calculated_balance
    summary, created = DailyCashSummary.objects.update_or_create(
        store=store, date=date,
        defaults={
            'opening_balance': opening_balance,
            'closing_balance': closing_balance,
            'calculated_balance': calculated_balance,
            'note': 'Closed manually by user',
        }
    )
    return JsonResponse({'success': True, 'created': created, 'summary_id': summary.id})

