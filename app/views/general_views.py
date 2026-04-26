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

# In your views.py
from django.contrib import messages
from django.contrib.auth.models import User
from datetime import datetime




@login_required
def index_view(request):
    from app.selectors.transaction_selectors import get_order_statistics
    from django.core.serializers import serialize
    from django.db.models import QuerySet
    from decimal import Decimal
    import json
    from datetime import date, timedelta

    user = request.user

    # Helper function to serialize querysets
    def serialize_queryset(queryset, fields=None):
        if not queryset:
            return []
        if isinstance(queryset, QuerySet):
            return list(queryset.values(*fields) if fields else queryset.values())
        return []

    # Helper function to handle decimals
    def decimal_to_float(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return obj

    # Get top selling products with proper serialization
    top_selling_products_qs = get_top_selling_products(limit=5)
    top_selling_products = []
    for product in top_selling_products_qs:
        top_selling_products.append({
            'id': product.get('product__id'),
            'name': product.get('product__name'),
            'total_sold': decimal_to_float(product.get('total_sold', 0)),
        })

    # Get low stock products with proper serialization
    low_stock_products_qs = get_low_stock_products(limit=5)
    low_stock_products = []
    for inventory in low_stock_products_qs:
        low_stock_products.append({
            'id': inventory.product.id,
            'name': inventory.product.name,
            'sku': inventory.product.sku,
            'quantity_in_stock': inventory.quantity_in_stock,
            'reorder_level': inventory.reorder_level,
            'store': inventory.store.name,
        })

    # Get recent stock adjustments with proper serialization
    recent_stock_adjustments_qs = get_recent_stock_adjustments(10)
    recent_stock_adjustments = []
    for adj in recent_stock_adjustments_qs:
        recent_stock_adjustments.append({
            'id': adj.id,
            'reference': adj.reference,
            'product': {
                'id': adj.product.id,
                'name': adj.product.name,
            },
            'store': {
                'id': adj.store.id,
                'name': adj.store.name,
            },
            'quantity_change': adj.quantity_change,
            'ui_quantity_change': adj.ui_quantity_change,
            'status': adj.status,
            'created_at': adj.created_at.isoformat(),
            'created_by': {
                'id': adj.created_by.id,
                'username': adj.created_by.username,
                'first_name': adj.created_by.first_name,
                'last_name': adj.created_by.last_name,
            },
            'reason': adj.reason,
            'unit_cost': decimal_to_float(adj.unit_cost) if adj.unit_cost else None,
        })

    # Get recent sales transactions
    recent_sales_qs = get_recent_sales(user, limit=5)
    recent_sales_transactions = []
    for sale in recent_sales_qs:
        recent_sales_transactions.append({
            'id': sale.id,
            'receipt_no': sale.receipt_no,
            'sale_date': sale.sale_date.isoformat(),
            'customer': sale.customer.name if sale.customer else 'Walk-in',
            'customer_id': sale.customer.id if sale.customer else None,
            'status': sale.status,
            'total_amount': decimal_to_float(sale.total_amount),
            'amount_paid': decimal_to_float(sale.amount_paid),
            'balance': decimal_to_float(sale.balance),
            'is_cancelled': sale.is_cancelled,
        })

    # Get recent purchase orders
    recent_purchases_qs = get_all_orders().order_by('-purchase_date')[:5]
    recent_purchase_orders = []
    for purchase in recent_purchases_qs:
        recent_purchase_orders.append({
            'id': purchase.id,
            'purchase_date': purchase.purchase_date.isoformat(),
            'supplier': purchase.supplier.name,
            'supplier_id': purchase.supplier.id,
            'status': purchase.status,
            'total_cost': decimal_to_float(purchase.total_cost),
            'note': purchase.note,
        })

    # Get recent expenses
    recent_expenses_qs = get_all_expenses().order_by('-date')[:5]
    recent_expenses = []
    for expense in recent_expenses_qs:
        recent_expenses.append({
            'id': expense.id,
            'date': expense.date.isoformat(),
            'amount': decimal_to_float(expense.amount),
            'description': expense.description,
            'category': expense.category.name if expense.category else None,
            'category_id': expense.category.id if expense.category else None,
            'store': expense.store.name,
            'store_id': expense.store.id,
            'reference': expense.reference,
        })

    # Get top customers
    top_customers_qs = get_top_customers(limit=5)
    top_customers = []
    for customer in top_customers_qs:
        top_customers.append({
            'id': customer.id,
            'name': customer.name,
            'email': customer.email,
            'phone': customer.phone,
            'total_sales': decimal_to_float(customer.total_sales) if hasattr(customer, 'total_sales') else 0,
            'total_orders': customer.total_orders if hasattr(customer, 'total_orders') else 0,
        })

    # Get top categories
    top_categories_qs = get_top_categories_by_sales(limit=3)
    top_categories = []
    for category in top_categories_qs:
        top_categories.append({
            'id': category.id,
            'name': category.name,
            'total_sales': decimal_to_float(category.total_sales) if hasattr(category, 'total_sales') else 0,
            'no_of_products': category.no_of_products,
        })

    # Get order statistics
    order_stats_data = get_order_statistics(days=7, user=user)
    order_stats = []
    for stat in order_stats_data:
        order_stats.append({
            'date': stat['date'],
            'count': stat['count'],
            'total': decimal_to_float(stat['total']),
        })

    # Prepare chart data for sales vs purchases
    # Get actual data for last 30 days
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    # You would implement these functions or use existing ones
    # For now using sample data structure
    sales_chart_data = {
        'labels': [],
        'purchases': [],
        'sales': [],
    }
    
    # Generate last 30 days labels
    for i in range(30):
        current_date = start_date + timedelta(days=i)
        sales_chart_data['labels'].append(current_date.strftime('%d %b'))

    # Prepare revenue vs expense chart data
    revenue_chart_data = {
        'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        'revenue': [],  # Populate with actual monthly revenue
        'expenses': [], # Populate with actual monthly expenses
    }

    # Prepare top categories chart
    top_categories_chart = {
        'labels': [c['name'] for c in top_categories],
        'data': [c['total_sales'] for c in top_categories],
    }

    # Prepare customer chart data
    customer_chart_data = {
        "labels": ["First Time", "Return"],
        "data": [6500, 4500],
    }

    context = {
        "organization_details": get_organization_settings(),
        "stores": serialize_queryset(get_stores(), ['id', 'name', 'branch_id', 'is_active']),

        # Financials
        "total_sales_per_user": decimal_to_float(get_total_sales_per_user(user)),
        "total_sales": decimal_to_float(get_total_sales()),
        "total_purchases": decimal_to_float(get_total_purchases()),
        "total_expenses": decimal_to_float(get_total_expenses()),
        "net_profit": decimal_to_float((get_total_sales() or 0) - (get_total_expenses() or 0)),
        "net_profit_per_user": decimal_to_float((get_total_sales_per_user(user) or 0) - (get_total_expenses() or 0)),
        "total_revenue": decimal_to_float(get_total_revenue()),
        "total_payments_received": decimal_to_float(get_total_payments_received(user)),

        # Counts
        "total_customers": get_number_of_customers(),
        "total_suppliers": get_number_of_suppliers(),
        "total_sale_orders": get_all_sales(user).count(),

        # Today's sales metrics
        "todays_number_sales": get_todays_number_of_sales(user),
        "todays_collection_rate": decimal_to_float(get_todays_collection_rate(user)),
        "todays_fully_paid_sales": get_todays_fully_paid_sales(user),
        "todays_partially_paid_sales": get_todays_partially_paid_sales(user),

        # Products
        "recent_sales": recent_sales_transactions,
        "low_stock_products": low_stock_products,
        "top_selling_products": top_selling_products,

        # Stock Adjustments
        "todays_stock_adjustments_count": get_todays_stock_adjustments().count(),
        "pending_stock_adjustments_count": get_pending_stock_adjustments_count(),
        "recent_stock_adjustments": recent_stock_adjustments,

        # Top Customers
        "top_customers": top_customers,

        # Top Categories
        "top_categories": top_categories,
        "total_categories": get_all_categories().count(),
        "total_products": get_all_products().count(),

        "hide_sidebar": True,
        
        # Chart data (JSON serialized)
        "order_stats_json": json.dumps(order_stats),
        "sales_chart_data_json": json.dumps(sales_chart_data),
        "revenue_chart_data_json": json.dumps(revenue_chart_data),
        "top_categories_chart_json": json.dumps(top_categories_chart),
        "customer_chart_data_json": customer_chart_data,
        # "customer_chart_data_json": json.dumps(customer_chart_data),

        # Recent Transactions
        "recent_sales_transactions": recent_sales_transactions,
        "recent_purchase_orders": recent_purchase_orders,
        "recent_expenses": recent_expenses,
        "recent_quotations": [],  # Add if you have quotations
        "recent_invoices": [],    # Add if you have invoices
    }

    # Dashboard modules logic remains the same
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

    if user.is_superuser and not dashboard_templates:
        from app.utils.dashboard_assignment import DASHBOARD_TEMPLATE_MAP
        dashboard_templates = list(DASHBOARD_TEMPLATE_MAP.values())
        dashboard_info = [
            {"name": name, "template": template}
            for name, template in DASHBOARD_TEMPLATE_MAP.items()
        ]

    # Enforce admin dashboard visibility restriction:
    # Only superusers should see the admin dashboard template.
    if not user.is_superuser and dashboard_templates:
        filtered_templates = []
        filtered_info = []
        for info in dashboard_info:
            template_path = info.get("template") or ""
            if "dashboards/admin.html" in template_path:
                continue
            filtered_templates.append(template_path)
            filtered_info.append(info)
        dashboard_templates = filtered_templates
        dashboard_info = filtered_info

    context.update({
        "dashboard_templates": dashboard_templates,
        "dashboard_info": dashboard_info,
    })

    return render(request, "basic/index.html", context)





@login_required
def orders_by_date(request):
    date_str = request.GET.get('date')
    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        orders = get_all_sales(request.user).filter(sale_date=date)[:10]
        orders_data = [{
            'id': order.id,
            'customer': str(order.customer),
            'total': float(order.total_amount),
            'status': order.status,
            'status_color': 'success' if order.is_fully_paid else 'warning' if order.is_partially_paid else 'danger'
        } for order in orders]
        return JsonResponse({'orders': orders_data})
    return JsonResponse({'orders': []})


def login_view(request):
    # Check if user was redirected due to session timeout
    timeout_message = None
    if request.GET.get('timeout'):
        timeout_message = "Your session has expired due to inactivity. Please log in again."
    
    # Check for messages from password reset
    default_password_notification = None
    username_for_reset = None
    
    # Check session for reset success
    if request.session.get('password_reset_success'):
        default_password_notification = request.session.get('password_reset_message')
        username_for_reset = request.session.get('reset_username')
        # Clear session data
        request.session.pop('password_reset_success', None)
        request.session.pop('password_reset_message', None)
        request.session.pop('reset_username', None)
    
    if request.method == "POST":
        # Only handle login POST requests
        form = AuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Clear any timeout warnings from session
            request.session.pop('timeout_warning', None)
            return redirect(index_view)
    
    else:
        # GET request - show empty form
        form = AuthenticationForm()
    
    context = {
        'form': form,
        'timeout_message': timeout_message,
        'default_password_notification': default_password_notification,
        'username': username_for_reset
    }
    
    return render(request, 'registration/login.html', context)



def reset_password_view(request):
    """Handle password reset AJAX requests"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        
        if not username:
            return JsonResponse({
                'success': False,
                'error': 'Please enter a username'
            })
        
        try:
            user = User.objects.get(username=username)
            # Set default password
            DEFAULT_PASSWORD = 'user_1234'
            user.set_password(DEFAULT_PASSWORD)
            user.save()
            
            # Store success in session for login page
            request.session['password_reset_success'] = True
            request.session['password_reset_message'] = f'Password has been reset for {username}. Default password: {DEFAULT_PASSWORD}'
            request.session['reset_username'] = username
            
            return JsonResponse({
                'success': True,
                'message': f'Password has been reset for {username}',
                'username': username,
                'default_password': DEFAULT_PASSWORD
            })
            
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'User "{username}" not found. Please check the username.'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })


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






