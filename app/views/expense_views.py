from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from app.models.expense import Expense, ExpenseCategory
from app.forms.expense_forms import ExpenseForm, ExpenseCategoryForm
from django.contrib import messages
from app.selectors.expense_selectors import *
from app.utils.list_helpers import list_context, options_from_queryset, panel_action

@login_required
def expense_list_view(request):
    # Example: filter by store if needed, or use all
    store = request.GET.get('store')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    expenses = get_expenses_for_store(store, start_date, end_date) if store else get_all_expenses()

    category_filter = request.GET.get('category', '').strip()
    if category_filter:
        expenses = expenses.filter(category_id=category_filter)

    # Calculate total expenses
    total_expenses = get_total_expenses(store, start_date, end_date) if store else get_total_expenses()

    # Get expenses by category
    expenses_by_category = get_expenses_by_category(store, start_date, end_date) if store else get_expenses_by_category()

    form = ExpenseForm()

    context = list_context(
        request,
        expenses,
        search_fields=('description', 'reference', 'user', 'category__name'),
        filters=[
            {
                'name': 'category',
                'label': 'All Categories',
                'options': options_from_queryset(
                    ExpenseCategory.objects.all(), value_field='pk', label_field='name',
                ),
            },
        ],
    )

    context.update({
        'expenses': context['page_obj'].object_list,
        'total_expenses': total_expenses,
        'expenses_by_category': expenses_by_category,
        'form': form,
        'search_placeholder': 'Search description, reference or user',
        'toolbar_label': 'expenses',
        'empty_title': 'No expenses found',
        'empty_text': 'Record an expense to track what your business spends on.',
        'empty_action_href': '#',
        'empty_action_target': '#add-expense',
        'empty_action_label': 'Add expense',
        'empty_icon': 'credit-card',
    })

    rows = []
    for expense in context['expenses']:
        detail_url = reverse('expense_detail_page', args=[expense.pk])
        panel_id = f'app-panel-expense-{expense.pk}'
        meta_parts = [expense.date.strftime('%d %b %Y') if expense.date else '']
        if expense.store:
            meta_parts.append(str(expense.store))
        if expense.user:
            meta_parts.append(expense.user)

        badges = []
        if expense.category:
            badges.append({'label': expense.category.name, 'tone': 'default'})
        if expense.attachment:
            badges.append({'label': 'Attachment', 'tone': 'info'})

        actions = [
            panel_action(panel_id),
            {'label': 'View expense', 'icon': 'eye', 'href': detail_url},
            {
                'label': 'Edit expense',
                'icon': 'edit',
                'href': '#',
                'attrs': {
                    'data-bs-toggle': 'modal',
                    'data-bs-target': '#add-expense',
                    'data-edit-url': reverse('edit_expense_page', args=[expense.pk]),
                    'data-expense-category': expense.category.name if expense.category else '',
                    'data-expense-amount': expense.amount,
                    'data-expense-date': expense.date.isoformat() if expense.date else '',
                    'data-expense-description': expense.description,
                    'data-expense-reference': expense.reference or '',
                    'data-expense-user': expense.user or '',
                },
            },
        ]
        if expense.attachment:
            actions.append({
                'label': 'Open attachment',
                'icon': 'paperclip',
                'href': expense.attachment.url,
                'attrs': {'target': '_blank'},
            })

        rows.append({
            'icon': 'credit-card',
            'category': 'expense',
            'title': expense.description or (expense.category.name if expense.category else 'Expense'),
            'meta': ' · '.join(part for part in meta_parts if part),
            'href': detail_url,
            'badges': badges,
            'fields': [
                {'label': 'Amount', 'value': f'{expense.amount:,.0f}'},
                {'label': 'Reference', 'value': expense.reference or '—'},
            ],
            'actions': actions,
            'panel_id': panel_id,
            'panel': {
                'title': expense.description or (expense.category.name if expense.category else 'Expense'),
                'subtitle': expense.category.name if expense.category else 'Uncategorised expense',
                'fields': [
                    {'label': 'Amount', 'value': f'{expense.amount:,.0f}'},
                    {'label': 'Date', 'value': expense.date.strftime('%d %b %Y') if expense.date else '—'},
                    {'label': 'Store', 'value': str(expense.store) if expense.store else '—'},
                    {'label': 'Recorded by', 'value': expense.user or '—'},
                    {'label': 'Reference', 'value': expense.reference or '—'},
                    {'label': 'Payment', 'value': str(expense.payment_method) if expense.payment_method else '—'},
                ],
                'href': detail_url,
            },
        })
    context['rows'] = rows

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

    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully.')
        return redirect('expense_list')
    return render(request, 'expenses/expense_confirm_delete.html', {'expense': expense})


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
            return redirect('expensecategory_list')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = ExpenseCategoryForm()
    return render(request, 'expenses/expense_category_form.html', {'form': form})

@login_required
def update_expensecategory_view(request, pk):
    category = get_object_or_404(ExpenseCategory, pk=pk)

    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense category updated successfully.')
            return redirect('expensecategory_list')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = ExpenseCategoryForm(instance=category)
    return render(request, 'expenses/expense_category_form.html', {'form': form, 'category': category})

@login_required
def expensecategory_delete(request, pk):
    category = get_object_or_404(ExpenseCategory, pk=pk)

    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Expense category deleted successfully.')
        return redirect('expensecategory_list')
    return render(request, 'expenses/expense_category_confirm_delete.html', {'category': category})
    
# form = ExpenseCategoryForm(instance=category)