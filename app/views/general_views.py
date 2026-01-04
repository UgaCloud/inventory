from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import time

from app.selectors.organization_selectors import *
from app.selectors.product_selectors import *
from app.selectors.transaction_selectors import *
from app.selectors.expense_selectors import get_total_expenses, get_all_expenses
from app.selectors.customer_selectors import *
from app.selectors.product_selectors import get_top_categories_by_sales
from app.selectors.supplier_selectors import *

from app.models.human_resource import UserProfile
from app.models.expense import Expense
from django.db.models import Sum







@login_required
def index_view(request):
        from app.selectors.transaction_selectors import get_order_statistics

        user = request.user

        context = {
            "organization_details": get_organization_settings(),
            "stores": get_stores(),

            # Financials
            "total_sales": get_total_sales(user),
            "total_purchases": get_total_purchases(),
            "total_expenses": get_total_expenses(),
            "net_profit": (get_total_sales(user) or 0) - (get_total_expenses() or 0),
            "total_revenue": get_total_revenue(),
            "total_payments_received": get_total_payments_received(user),

            # Counts
            "total_customers": get_number_of_customers(),
            "total_suppliers": get_number_of_suppliers(),
            "total_sale_orders": get_all_sales(user).count(),

            # Today's sales metrics
            "todays_number_sales": get_todays_number_of_sales(user),
            "todays_collection_rate": get_todays_collection_rate(user),
            "todays_fully_paid_sales": get_todays_fully_paid_sales(user),
            "todays_partially_paid_sales": get_todays_partially_paid_sales(user),
            # "todays_unpaid_sales": get_todays_unpaid_sales(user),

            # Products
            "recent_sales": get_recent_sales(user, limit=5),
            "low_stock_products": get_low_stock_products(),
            "top_selling_products": get_top_selling_products(),

            # Stock Adjustments
            "todays_stock_adjustments_count": get_todays_stock_adjustments().count(),
            "pending_stock_adjustments_count": get_pending_stock_adjustments_count(),
            "recent_stock_adjustments": get_recent_stock_adjustments(10),

            # Top Customers (by total sales amount)
            "top_customers": get_top_customers(limit=5),

            # Top Categories (by sales)
            "top_categories": get_top_categories_by_sales(limit=3),
            "total_categories": get_all_categories().count(),
            "total_products": get_all_products().count(),

            "hide_sidebar": True,
            # Order statistics for last 7 days
            "order_stats": get_order_statistics(days=7, user=user),
        }

        # Recent Transactions (dynamic for dashboard tabs)
        recent_sales_transactions = get_recent_sales(user, limit=5)
        recent_purchase_orders = get_all_orders().order_by('-purchase_date')[:5]
        recent_expenses = get_all_expenses().order_by('-date')[:5]
        # For quotations and invoices, use Sales with status or a dedicated model if available
        recent_quotations = get_all_sales(user).filter(status='quotation').order_by('-sale_date')[:5]
        recent_invoices = get_all_sales(user).filter(status='invoice').order_by('-sale_date')[:5]

        context.update({
            "recent_sales_transactions": recent_sales_transactions,
            "recent_purchase_orders": recent_purchase_orders,
            "recent_expenses": recent_expenses,
            "recent_quotations": recent_quotations,
            "recent_invoices": recent_invoices,
        })
        dashboard_templates = []
        dashboard_info = []

        try:
            from app.utils.dashboard_assignment import (
                get_dashboard_templates_for_modules,
                get_dashboard_info_for_modules,
            )
            modules = user.profile.effective_modules
            dashboard_info = get_dashboard_info_for_modules(modules)
            dashboard_templates = [item["template"] for item in dashboard_info]
        except (UserProfile.DoesNotExist, AttributeError):
            pass

        # Superuser fallback
        if user.is_superuser and not dashboard_templates:
            from app.utils.dashboard_assignment import DASHBOARD_TEMPLATE_MAP
            dashboard_templates = list(DASHBOARD_TEMPLATE_MAP.values())
            dashboard_info = [
                {"name": name, "template": template}
                for name, template in DASHBOARD_TEMPLATE_MAP.items()
            ]

        context.update({
            "dashboard_templates": dashboard_templates,
            "dashboard_info": dashboard_info,
        })

        return render(request, "basic/index.html", context)




# Restore login_view as a standalone function
def login_view(request):
    # Check if user was redirected due to session timeout
    timeout_message = None
    if request.GET.get('timeout'):
        timeout_message = "Your session has expired due to inactivity. Please log in again."

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Clear any timeout warnings from session
            request.session.pop('timeout_warning', None)
            return redirect(index_view)

    else:
        form = AuthenticationForm()

    context = {
        'form': form,
        'timeout_message': timeout_message
    }

    return render(request, 'registration/login.html', context)

@login_required
def sign_up_view(request):
    message = ''
    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password('user1234')
            user.save()
            message = 'Data has been succeefully stored in the database. Default password is user1234.'
            return redirect('login')
    else:
        form = UserCreationForm()

    context = {
        'form':form,
        'message':message
    }
    return render(request, 'registration/sign_up.html', context)

@login_required
def under_maintenance_view(request):
    return render(request, 'under_maintenance.html')

@login_required
@require_http_methods(["POST"])
def extend_session_view(request):
    """
    Extend the user's session when they explicitly request it.
    """
    try:
        # Update session activity
        request.session['last_activity'] = time.time()
        request.session.set_expiry(None)  # Reset to default session age
        
        return JsonResponse({'success': True, 'message': 'Session extended successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required  
def logout_view(request):
    """
    Custom logout view with session cleanup.
    """
    # Clear session data
    request.session.flush()
    logout(request)
    return redirect('login')

