from django.shortcuts import render, redirect
from app.forms.customer_forms import CustomerForm
from app.selectors.customer_selectors import get_all_customers

def customer_view(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = CustomerForm()
    
    customers = get_all_customers()

    context = {
        'form':form,
        'customers':customers
    }
    return render(request, 'customers.html', context)