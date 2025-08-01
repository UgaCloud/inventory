from app.models.expense import Expense, ExpenseCategory
from django.db.models import Sum, Q
from datetime import date, timedelta

def get_expenses_for_store(store, start_date=None, end_date=None):
    qs = Expense.objects.filter(store=store)
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)
    return qs.order_by('-date')

def get_expenses_by_category(store=None, start_date=None, end_date=None):
    expenses = Expense.objects.all()
    if store:
        expenses = expenses.filter(store=store)
    if start_date:
        expenses = expenses.filter(date__gte=start_date)
    if end_date:
        expenses = expenses.filter(date__lte=end_date)
    return expenses.values('category__name').annotate(total=Sum('amount')).order_by('-total')

def get_total_expenses(store=None, start_date=None, end_date=None):
    qs = Expense.objects.all()
    if store:
        qs = qs.filter(store=store)
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)
    return qs.aggregate(total=Sum('amount'))['total'] or 0

def get_expenses_linked_to_purchase(purchase):
    return Expense.objects.filter(related_purchase=purchase)

def get_expenses_linked_to_sale(sale):
    return Expense.objects.filter(related_sale=sale)

def get_expenses_linked_to_cashflow(cashflow):
    return Expense.objects.filter(related_cashflow=cashflow)

def get_expenses_expiring_soon(days=30):
    soon = date.today() + timedelta(days=days)
    return Expense.objects.filter(date__lte=soon, date__gte=date.today())

def get_expense_by_id(expense_id):
    """Return a single expense by its primary key."""
    return Expense.objects.get(pk=expense_id)

def get_expense_categories():
    """Return all expense categories."""
    return ExpenseCategory.objects.all()

def get_expense_category_by_id(category_id):
    """Return a single expense category by its primary key."""
    return ExpenseCategory.objects.filter(pk=category_id).first()

def get_all_expenses():
    """Return all expenses."""
    return Expense.objects.all().order_by('-date')

def get_expenses_by_user(user):
    """Return all expenses created by a specific user."""
    return Expense.objects.filter(user=user).order_by('-date')


