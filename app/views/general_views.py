from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required

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

    low_stock_products = get_low_stock_products()
    top_selling_products = get_top_selling_products()
    recent_sales = get_recent_sales(limit=5)

    print("Recent Sales:", recent_sales)

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
    }
    return render(request, 'basic/index.html', context)

@login_required
def login_view(request):

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(index_view)

    else:
        form = AuthenticationForm()

    context = {
        'form':form
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

