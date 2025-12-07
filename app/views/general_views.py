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
from app.models.human_resource import UserProfile




@login_required
def index_view(request):
    products = get_all_products()
    organization_details = get_organization_settings()
    stores = get_stores()
    total_purchases = get_total_purchases()
    total_sales = get_total_sales()
    todays_number_sales = get_todays_number_of_sales()
    total_expenses = get_total_expenses()
    net_profit = get_net_profit()
    total_suppliers = get_number_of_suppliers()
    total_customers = get_number_of_customers()
    total_sale_orders = get_number_of_sales()
    total_payments_received = get_total_payments_received()
    total_outstanding_balances = get_total_outstanding_balances()
    todays_outstanding_balances = get_todays_outstanding_balances()
    todays_collection_rate = get_todays_collection_rate()
    low_stock_products = get_low_stock_products()
    top_selling_products = get_top_selling_products()
    recent_sales = get_recent_sales(limit=5)
    
    # Stock adjustment data
    recent_stock_adjustments = get_recent_stock_adjustments(limit=10)
    pending_stock_adjustments = get_pending_stock_adjustments()
    pending_stock_adjustments_count = get_pending_stock_adjustments_count()
    todays_stock_adjustments_count = get_todays_stock_adjustments_count()
    total_revenue = get_total_revenue()


    
    # Determine which dashboards to show based on RBAC module access
    # Uses the flexible dashboard assignment system
    dashboard_templates = []
    dashboard_info = []
    if request.user.is_authenticated:
        try:
            from app.utils.dashboard_assignment import (
                get_dashboard_templates_for_modules,
                get_dashboard_info_for_modules
            )
            accessible_modules = request.user.profile.effective_modules
            # Get dashboard info (name and template) automatically based on module access
            dashboard_info = get_dashboard_info_for_modules(accessible_modules)
            dashboard_templates = [info['template'] for info in dashboard_info]
            
            # Debug logging (remove in production if needed)
            print(f"🔍 User: {request.user.username}")
            print(f"🔍 Accessible modules: {accessible_modules}")
            print(f"🔍 Assigned dashboards: {[info['name'] for info in dashboard_info]}")
            
        except UserProfile.DoesNotExist:
            dashboard_templates = []
            dashboard_info = []
            print("⚠️ UserProfile does not exist for user:", request.user.username)
        except AttributeError as e:
            # Fallback if profile doesn't have effective_modules
            dashboard_templates = []
            dashboard_info = []
            print(f"⚠️ AttributeError accessing effective_modules: {e}")
    
    # Superusers: Only give all dashboards if they have no specific module-based dashboards
    # This prevents showing all dashboards when superuser has specific module access
    if request.user.is_superuser and not dashboard_templates:
        from app.utils.dashboard_assignment import DASHBOARD_TEMPLATE_MAP, DASHBOARD_MODULE_MAP
        dashboard_templates = list(DASHBOARD_TEMPLATE_MAP.values())
        dashboard_info = [
            {'name': name, 'template': template}
            for name, template in DASHBOARD_TEMPLATE_MAP.items()
        ]
        print(f"🔍 Superuser with no module dashboards - showing all: {dashboard_templates}")

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
        'todays_number_sales': todays_number_sales,
        'todays_credit_sales': todays_outstanding_balances,
        'todays_collection_rate': todays_collection_rate,
        'todays_fully_paid_sales': get_todays_fully_paid_sales(),
        'todays_partially_paid_sales': get_todays_partially_paid_sales(),
        'todays_unpaid_sales': get_todays_unpaid_sales(),
        'recent_stock_adjustments': recent_stock_adjustments,
        'pending_stock_adjustments': pending_stock_adjustments,
        'pending_stock_adjustments_count': pending_stock_adjustments_count,
        'todays_stock_adjustments_count': todays_stock_adjustments_count,
        'total_revenue': total_revenue,
        
        # ADD THIS LINE to hide sidebar on dashboard:
        'hide_sidebar': True,
        'dashboard_templates': dashboard_templates,
        'dashboard_info': dashboard_info,  # List of dicts with 'name' and 'template'
    }
    print(context['todays_fully_paid_sales'])
    
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

