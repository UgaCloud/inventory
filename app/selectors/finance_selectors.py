from app.models.finance import CashFlow, DailyCashSummary, BankAccount, BankTransaction
from app.models.transactions import PurchaseOrder, Sales
from app.models.expense import Expense
from django.db.models import Sum, Q
from datetime import date

def get_cashflows(store=None, start_date=None, end_date=None, transaction_type=None):
    qs = CashFlow.objects.all()
    if store:
        qs = qs.filter(store=store)
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)
    if transaction_type:
        qs = qs.filter(transaction_type=transaction_type)
    return qs

def get_cashflow_total(store=None, start_date=None, end_date=None, transaction_type=None):
    qs = get_cashflows(store, start_date, end_date, transaction_type)
    return qs.aggregate(total=Sum('amount'))['total'] or 0

def get_daily_cash_summaries(store=None, start_date=None, end_date=None):
    qs = DailyCashSummary.objects.all()
    if store:
        qs = qs.filter(store=store)
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)
    return qs

def get_bank_accounts(active_only=True):
    qs = BankAccount.objects.all()
    if active_only:
        qs = qs.filter(is_active=True)
    return qs

def get_bank_account(account_id):
    return BankAccount.objects.get(id=account_id)

def get_bank_transactions(bank_account=None, store=None, start_date=None, end_date=None, transaction_type=None):
    qs = BankTransaction.objects.all()
    if bank_account:
        qs = qs.filter(bank_account=bank_account)
    if store:
        qs = qs.filter(store=store)
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)
    if transaction_type:
        qs = qs.filter(transaction_type=transaction_type)
    return qs

def get_bank_transaction(transaction_id):
    return BankTransaction.objects.get(id=transaction_id)

def get_bank_balance(bank_account):
    deposits = BankTransaction.objects.filter(bank_account=bank_account, amount__gt=0).aggregate(total=Sum('amount'))['total'] or 0
    withdrawals = BankTransaction.objects.filter(bank_account=bank_account, amount__lt=0).aggregate(total=Sum('amount'))['total'] or 0
    return (bank_account.opening_balance or 0) + deposits + withdrawals

def get_cashflow_for_bank_transaction(bank_transaction):
    return bank_transaction.related_cashflow