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
from app.selectors.customer_selectors import *
from app.selectors.supplier_selectors import *


@login_required
def index_view(request):
    products = get_all_products()
    organization_details = get_organization_settings()
    stores = get_stores()
    
    total_purchases = get_total_purchases()
    total_sales = get_total_sales()
    total_expenses = get_total_expenses()
    net_profit = get_net_profit()
    total_suppliers = get_number_of_suppliers()
    total_customers = get_number_of_customers()
    total_sale_orders = get_number_of_sales()
    total_payments_received = get_total_payments_received()
    total_outstanding_balances = get_total_outstanding_balances()

    low_stock_products = get_low_stock_products()
    top_selling_products = get_top_selling_products()
    recent_sales = get_recent_sales(limit=5)

    context = {
        'products': products,
        'organization_details': organization_details,
        'stores': stores,
        'total_purchases': total_purchases,
        'total_sales': total_sales,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'total_suppliers': total_suppliers,
        'total_customers': total_customers,
        'total_sale_orders': total_sale_orders,
        'low_stock_products': low_stock_products,
        'top_selling_products': top_selling_products,
        'recent_sales': recent_sales,
        'total_payments_received': total_payments_received,
        'total_outstanding_balances': total_outstanding_balances,
    }
    # context = {
    # 'current_store': current_store,
    # 'total_products': total_products,
    # 'low_stock_count': low_stock_count,
    # 'pending_transfers': pending_transfers,
    # 'today_sales': today_sales,
    # 'low_stock_products': low_stock_products,
    # 'recent_activities': recent_activities,
    # # 'my_transfer_requests': my_transfer_requests,
    # # 'stock_received_today': stock_received_today,
    # 'stock_sold_today': stock_sold_today,
    # # 'top_moving_products': top_moving_products,
    # # 'total_inventory_value': total_inventory_value,
    # 'critical_alerts': critical_alerts,
# }
    return render(request, 'basic/index.html', context)

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
            form.save()
            message = 'Data has been succeefully stored in the database'
            return redirect(login_view)
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

