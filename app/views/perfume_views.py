from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST

from app.models.customers import Customer
from app.models.finance import PaymentMethod
from app.models.products import Product, StoreLocation
from app.services.perfume_service import (
    estimate_stock_cost,
    get_ml_unit_price,
    get_perfume_products,
    record_perfume_sale,
)


@login_required
@require_POST
def record_perfume_sale_view(request):
    """
    Record a perfume sale (single perfume by ml, or a mixture of 2+ perfumes)
    posted from the perfume panel on the record-sale page. Uses PRG so a
    refresh cannot resubmit the sale.
    """
    store = StoreLocation.objects.filter(
        pk=request.POST.get('store') or 0
    ).first()
    if store is None:
        store = StoreLocation.objects.filter(is_default=True).first()
    if store is None:
        store = StoreLocation.objects.first()
    if store is None:
        messages.error(request, "No store is configured; cannot record a sale.")
        return redirect('record_sale')

    products = request.POST.getlist('component_product')
    quantities = request.POST.getlist('component_ml')

    components = []
    for product_id, quantity_ml in zip(products, quantities):
        if not str(product_id).strip():
            continue
        product = Product.objects.filter(pk=product_id, is_active=True).first()
        if product is None:
            messages.error(request, f"Unknown or inactive product (id {product_id}).")
            return redirect('record_sale')
        components.append((product, quantity_ml))

    customer = None
    customer_id = request.POST.get('customer')
    if customer_id:
        customer = Customer.objects.filter(pk=customer_id, is_active=True).first()

    payment_method = None
    payment_method_id = request.POST.get('payment_method')
    if payment_method_id:
        payment_method = PaymentMethod.objects.filter(pk=payment_method_id).first()

    try:
        sale = record_perfume_sale(
            store=store,
            components=components,
            selling_price=request.POST.get('selling_price'),
            user=request.user,
            customer=customer,
            amount_paid=request.POST.get('amount_paid') or 0,
            amount_received=request.POST.get('amount_received') or 0,
            payment_method=payment_method,
            note=request.POST.get('note', '').strip(),
        )
    except ValidationError as e:
        for message in e.messages:
            messages.error(request, message)
        return redirect('record_sale')

    mixture_label = "mixture" if len(components) > 1 else "perfume sale"
    messages.success(
        request,
        f"Perfume {mixture_label} recorded on sale #{sale.receipt_no} "
        f"({sale.perfume_lines.first().total_quantity_ml:g} ml for "
        f"UGX {sale.total_amount:,})."
    )
    return redirect('sales_detail', pk=sale.pk)


@login_required
@require_GET
def perfume_stock_info(request):
    """
    JSON: available stock (base units) and current FIFO cost per base unit for
    a product in a store. Used by the perfume panel to preview cost/profit.
    """
    product = Product.objects.filter(pk=request.GET.get('product_id')).first()
    store = StoreLocation.objects.filter(pk=request.GET.get('store_id')).first()
    if product is None or store is None:
        return JsonResponse({'error': 'product_id and store_id are required'}, status=400)

    available, cost_per_unit = estimate_stock_cost(product, store)
    unit_price_row = get_ml_unit_price(product)
    return JsonResponse({
        'product': product.name,
        'store': store.name,
        'available': available,
        'unit_name': unit_price_row.unit.name if unit_price_row else 'ml',
        'conversion_factor': int(unit_price_row.conversion_factor) if unit_price_row else 1,
        'cost_per_unit': float(cost_per_unit) if cost_per_unit is not None else None,
    })


@login_required
def record_sale_page_context(request):
    """Shared context for the perfume panel rendered on record_sales.html."""
    return {
        'perfume_products': get_perfume_products(),
        'perfume_customers': Customer.objects.filter(is_active=True).order_by('name'),
        'perfume_payment_methods': PaymentMethod.objects.filter(is_active=True).order_by('name'),
        'perfume_stores': StoreLocation.objects.filter(is_active=True).order_by('name'),
    }
