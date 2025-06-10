from django.shortcuts import render, redirect
from app.forms.customer_forms import CustomerForm
from app.selectors.customer_selectors import get_all_customers

def customer_view(request):
    return render(request, 'customer_list.html')

def add_customer_view(request):
    return render(request, 'add_customer.html')