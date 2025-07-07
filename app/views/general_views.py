from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from app.selectors.product_selectors import get_all_products
from django.views.generic import View
from app.models.suppliers import Supplier
from app.models.transactions import StockTransfer


def index_view(request):
    products = get_all_products()
    context = {
        'products':products
    }
    return render(request, 'basic/index.html', context)

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

#class based view to handle deletions from the supplier and stock transfer models
class DeleteMultipleSuppliers(View):
    def post(self, request):
        selected_ids = request.POST.getlist('selected_items')

        if selected_ids:
            Supplier.objects.filter(id__in = selected_ids).delete()
            StockTransfer.objects.filter(id__in = selected_ids).delete()
            
        return redirect(request.META.get('HTTP_REFERER')) # redirect to where the request came from

def under_maintenance_view(request):
    return render(request, 'under_maintenance.html')
        
        