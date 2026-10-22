from django.shortcuts import render, redirect, get_object_or_404
from app.forms.suppliers_form import SupplierForm, Supplier
from django.contrib import messages
from app.selectors.supplier_selectors import get_all_suppliers
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from app.utils.list_helpers import list_context, panel_action


@login_required
def supplier_view(request):
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier created successfully.')
            return redirect('supplier_page')
    else:
        form = SupplierForm()

    suppliers = get_all_suppliers()
    status_filter = request.GET.get('status', '').strip()
    if status_filter == 'active':
        suppliers = suppliers.filter(is_active=True)
    elif status_filter == 'inactive':
        suppliers = suppliers.filter(is_active=False)

    context = list_context(
        request,
        suppliers,
        search_fields=('name', 'contact_person', 'email', 'phone', 'supplier_code'),
        filters=[
            {
                'name': 'status',
                'label': 'All Status',
                'options': [
                    {'value': 'active', 'label': 'Active'},
                    {'value': 'inactive', 'label': 'Inactive'},
                ],
            },
        ],
    )
    context.update({
        'form': form,
        'suppliers': context['page_obj'].object_list,
        'search_placeholder': 'Search name, contact or email',
        'toolbar_label': 'suppliers',
        'empty_title': 'No suppliers found',
        'empty_text': 'Add a supplier to track purchase orders and payments.',
        'empty_action_href': '#',
        'empty_action_target': '#add-supllier',
        'empty_action_label': 'Add supplier',
        'empty_icon': 'truck',
    })

    rows = []
    for supplier in context['suppliers']:
        meta_parts = [part for part in [supplier.contact_person, supplier.email, supplier.phone] if part]
        panel_id = f'app-panel-supplier-{supplier.pk}'
        rows.append({
            'icon': 'truck',
            'category': 'supplier',
            'title': supplier.name,
            'meta': ' · '.join(meta_parts) or 'No contact details',
            'badges': (
                [{'label': 'Active', 'tone': 'success'}]
                if supplier.is_active else [{'label': 'Inactive', 'tone': 'danger'}]
            ),
            'fields': [
                {'label': 'Code', 'value': supplier.supplier_code or '—'},
                {'label': 'Terms', 'value': supplier.payment_terms or '—'},
            ],
            'actions': [
                panel_action(panel_id),
                {
                    'label': 'Edit supplier',
                    'icon': 'edit',
                    'href': '#',
                    'attrs': {
                        'data-bs-toggle': 'modal',
                        'data-bs-target': '#add-supllier',
                        'data-edit-url': reverse('edit_supplier_page', args=[supplier.pk]),
                        'data-supplier-name': supplier.name,
                        'data-supplier-contact-person': supplier.contact_person or '',
                        'data-supplier-email': supplier.email or '',
                        'data-supplier-address': supplier.address or '',
                    },
                },
            ],
            'panel_id': panel_id,
            'panel': {
                'title': supplier.name,
                'subtitle': supplier.supplier_code or 'Supplier record',
                'fields': [
                    {'label': 'Contact', 'value': supplier.contact_person or '—'},
                    {'label': 'Email', 'value': supplier.email or '—'},
                    {'label': 'Phone', 'value': supplier.phone or '—'},
                    {'label': 'Terms', 'value': supplier.payment_terms or '—'},
                    {'label': 'Status', 'value': 'Active' if supplier.is_active else 'Inactive'},
                    {'label': 'Address', 'value': supplier.address or '—'},
                ],
                'note': supplier.notes or '',
            },
        })
    context['rows'] = rows

    return render(request, 'stock/supplier.html', context)

@login_required
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