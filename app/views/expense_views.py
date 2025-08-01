from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from app.models.expense import Expense, ExpenseCategory
from app.forms.expense_forms import ExpenseForm, ExpenseCategoryForm
from django.contrib import messages
from app.selectors.expense_selectors import *

@login_required
def expense_list_view(request):
    # Example: filter by store if needed, or use all
    store = request.GET.get('store')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    expenses = get_expenses_for_store(store, start_date, end_date) if store else get_all_expenses()

    # Calculate total expenses
    total_expenses = get_total_expenses(store, start_date, end_date) if store else get_total_expenses()

    # Get expenses by category
    expenses_by_category = get_expenses_by_category(store, start_date, end_date) if store else get_expenses_by_category()

    form = ExpenseForm()

    context = {
        'expenses': expenses,
        'total_expenses': total_expenses,
        'expenses_by_category': expenses_by_category,
        'form': form,
    }
    
    return render(request, 'expenses/expense_list.html', context)

@login_required
def expense_detail_view(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    
    linked_purchase_expenses = get_expenses_linked_to_purchase(expense.related_purchase) if expense.related_purchase else None
    
    linked_sale_expenses = get_expenses_linked_to_sale(expense.related_sale) if expense.related_sale else None
    
    linked_cashflow_expenses = get_expenses_linked_to_cashflow(expense.related_cashflow) if expense.related_cashflow else None
    
    form = ExpenseForm(instance=expense) 

    context = {
        'expense': expense,
        'linked_purchase_expenses': linked_purchase_expenses,
        'linked_sale_expenses': linked_sale_expenses,
        'linked_cashflow_expenses': linked_cashflow_expenses,
        'form': form
    }

    return render(request, 'expenses/expense_detail.html', context)

@login_required
def add_expense_view(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense created successfully.')
        return redirect(expense_list_view)
    else:
        form = ExpenseForm()
    return render(request, 'expenses/expense_form.html', {'form': form})

@login_required
def expense_update_view(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully.')
        return redirect(expense_detail_view, pk=expense.pk)
    else:
        form = ExpenseForm(instance=expense)
    return render(request, 'expenses/expense_form.html', {'form': form, 'expense': expense})

@login_required
def delete_expense_view(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    
    expense.delete()
    messages.success(request, 'Expense deleted successfully.')
    
    return redirect(expense_list_view)


@login_required
def expensecategory_list_view(request):
    categories = get_expense_categories()

    form = ExpenseCategoryForm()

    context = {
        'categories': categories,
        'form': form,
    }
    
    return render(request, 'expenses/expense_category_list.html', context)

@login_required
def add_expensecategory_view(request):
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense category created successfully.')
            
        return redirect(expensecategory_list_view)

@login_required
def update_expensecategory_view(request, pk):
    category = get_object_or_404(ExpenseCategory, pk=pk)
    
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=category)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense category updated successfully.')
            
        return redirect(expense_list_view)

@login_required
def expensecategory_delete(request, pk):
    category = get_object_or_404(ExpenseCategory, pk=pk)
    
    category.delete()
    messages.success(request, 'Expense category deleted successfully.')
    
    return redirect(expensecategory_list_view)
    
# form = ExpenseCategoryForm(instance=category)