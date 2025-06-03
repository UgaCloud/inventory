
from django.shortcuts import render, redirect
from app.forms.suppliers_form import SupplierForm
from app.selectors.supplier_selectors import get_all_suppliers

def supplier_view(request):
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = SupplierForm()

    suppliers = get_all_suppliers()

    context = {
         'form':form,
         'suppliers':suppliers
     }
    return render(request, 'supplier.html', context)