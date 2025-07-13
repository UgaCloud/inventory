
from django.shortcuts import render, redirect, get_object_or_404
from app.forms.suppliers_form import SupplierForm, Supplier
from django.contrib import messages
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
    return render(request, 'stock/supplier.html', context)

def edit_supplier_view(request, supplier_id):
    unit = get_object_or_404(Supplier, id=supplier_id)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=unit)
        if form.is_valid():
            form.save()
            messages.success(request, "Unit of Measure updated successfully.")
            return redirect(supplier_view)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SupplierForm(instance=unit)
    return redirect(supplier_view)