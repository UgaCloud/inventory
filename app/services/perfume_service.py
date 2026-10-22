"""
Service layer for recording perfume sales measured in millilitres.

Perfume sales (single or mixture) reuse the existing Sales record, Inventory,
InventoryBatch (FIFO costing) and StockMovement machinery. A mixture is stored
as one PerfumeSaleLine with one PerfumeSaleComponent per perfume: the mixture
itself never holds stock, so component stock is never duplicated.

Assumptions (documented minimal assumptions):
- Whole-number ml quantities only. Inventory/InventoryBatch/StockMovement use
  integer base units, so fractional ml cannot be tracked without widening the
  existing quantity schema.
- Each perfume must have an "ml" UnitOfMeasure with a ProductUnitPrice row;
  quantity_ml converts to base units with the same conversion machinery the
  rest of the system uses (convert_to_base_units).
- The mixture selling price is entered by the user (a blend has no single
  configured floor price), but must be a positive whole-shilling amount.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from app.models.customers import Payment
from app.models.perfume import PerfumeSaleComponent, PerfumeSaleLine
from app.models.products import Inventory, Product, ProductUnitPrice, UnitOfMeasure
from app.models.transactions import InventoryBatch, Sales, StockMovement
from app.utils.utils import convert_to_base_units


def get_ml_unit():
    """The Millilitre unit of measure, matched by abbreviation or name."""
    return (
        UnitOfMeasure.objects.filter(abbreviation__iexact='ml').first()
        or UnitOfMeasure.objects.filter(name__istartswith='milli').first()
    )


def get_perfume_products():
    """Active products that can be sold by the millilitre."""
    ml_unit = get_ml_unit()
    if not ml_unit:
        return Product.objects.none()
    return (
        Product.objects.filter(is_active=True, unit_prices__unit=ml_unit)
        .distinct()
        .order_by('name')
    )


def get_ml_unit_price(product):
    """The ProductUnitPrice row linking this product to the ml unit."""
    ml_unit = get_ml_unit()
    if not ml_unit:
        return None
    return ProductUnitPrice.objects.filter(product=product, unit=ml_unit).first()


def estimate_stock_cost(product, store):
    """
    Current available ml stock and FIFO cost per base unit for a product in a
    store. Used by the POS panel to preview cost/gross profit. Returns
    (available_base_units, cost_per_base_unit or None).
    """
    inventory = Inventory.objects.filter(product=product, store=store).first()
    if not inventory:
        return 0, None
    batches = InventoryBatch.objects.filter(
        Q(expiry_date__gte=timezone.now().date()) | Q(expiry_date__isnull=True),
        product=product,
        store=store,
        remaining_quantity__gt=0,
    ).order_by('expiry_date', 'received_date')
    total_remaining = 0
    total_value = Decimal('0')
    for batch in batches:
        total_remaining += batch.remaining_quantity
        total_value += Decimal(batch.remaining_quantity) * Decimal(batch.unit_cost)
    # Cap at recorded stock; extra committed stock is not visible here.
    available = min(total_remaining, inventory.quantity_in_stock)
    if total_remaining <= 0:
        return max(0, inventory.quantity_in_stock), None
    return available, (total_value / Decimal(total_remaining)).quantize(Decimal('0.0001'))


def _consume_stock_fifo(sale, product, base_quantity, user):
    """
    Deduct base_quantity from the product's batches (FIFO, expired batches
    skipped) and inventory in the sale's store, returning the actual cost
    consumed. Row locks (select_for_update) prevent concurrent overselling on
    backends that support it; Inventory.save() rejects negative stock on every
    backend. Raises ValidationError (rolling back the whole sale) if stock is
    insufficient.
    """
    inventory = (
        Inventory.objects.select_for_update()
        .filter(product=product, store=sale.store)
        .first()
    )
    if inventory is None:
        raise ValidationError(
            f"{product.name} has no inventory record in store '{sale.store.name}'."
        )
    if inventory.quantity_in_stock < base_quantity:
        raise ValidationError(
            f"Insufficient stock for {product.name} in store '{sale.store.name}': "
            f"available {inventory.quantity_in_stock}, requested {base_quantity}."
        )

    batches = list(
        InventoryBatch.objects.select_for_update()
        .filter(
            Q(expiry_date__gte=timezone.now().date()) | Q(expiry_date__isnull=True),
            product=product,
            store=sale.store,
            remaining_quantity__gt=0,
        )
        .order_by('expiry_date', 'received_date')
    )

    remaining = base_quantity
    cost = Decimal('0')
    for batch in batches:
        if remaining <= 0:
            break
        take = min(batch.remaining_quantity, remaining)
        cost += Decimal(take) * Decimal(batch.unit_cost)
        batch.remaining_quantity -= take
        batch.save(update_fields=['remaining_quantity'])
        remaining -= take

    if remaining > 0:
        raise ValidationError(
            f"Insufficient batch stock for {product.name} in store "
            f"'{sale.store.name}': {base_quantity - remaining} of "
            f"{base_quantity} available in batches."
        )

    inventory.quantity_in_stock -= base_quantity
    inventory.save(update_fields=['quantity_in_stock'])

    StockMovement.objects.create(
        product=product,
        store=sale.store,
        transaction_type='OUT',
        quantity=-base_quantity,
        transaction_id=sale.id,
        note='Perfume sale',
        units_in_stock=inventory.quantity_in_stock,
        user=str(user),
    )
    return cost


def record_perfume_sale(*, store, components, selling_price, user,
                        customer=None, amount_paid=0, amount_received=0,
                        payment_method=None, note=''):
    """
    Record a perfume sale (single perfume or mixture) atomically.

    components: iterable of (product, quantity_ml) pairs. quantity_ml must be
    a positive whole number of millilitres per product, no duplicates.

    Creates one Sales record with one PerfumeSaleLine and a
    PerfumeSaleComponent per perfume, deducts each component's stock from the
    store's inventory (FIFO batches), snapshots historical costs, and records
    a StockMovement per component. Either everything succeeds or nothing is
    saved.

    Returns the created Sales instance.
    Raises django.core.exceptions.ValidationError on any validation failure.
    """
    components = list(components)

    # ---- validate component list ----
    if not components:
        raise ValidationError("A perfume sale needs at least one perfume.")

    seen_products = set()
    normalized = []
    total_ml = Decimal('0')
    for product, quantity_ml in components:
        if product is None:
            raise ValidationError("Each perfume line must have a product.")
        if not product.is_active:
            raise ValidationError(f"Product '{product.name}' is not active.")
        try:
            qty = Decimal(str(quantity_ml))
        except Exception:
            raise ValidationError(f"Invalid quantity for {product.name}.")
        if qty <= 0:
            raise ValidationError(
                f"Quantity for {product.name} must be greater than zero."
            )
        if qty % 1 != 0:
            raise ValidationError(
                f"Quantity for {product.name} must be a whole number of "
                f"millilitres (fractional ml is not supported)."
            )
        if product.pk in seen_products:
            raise ValidationError(
                f"{product.name} appears more than once in the mixture. "
                f"Enter the combined quantity on a single line."
            )
        seen_products.add(product.pk)
        normalized.append((product, qty))
        total_ml += qty

    # ---- validate sale-level values ----
    try:
        price = Decimal(str(selling_price))
    except Exception:
        raise ValidationError("Invalid selling price.")
    if price <= 0:
        raise ValidationError("Selling price must be greater than zero.")
    if price % 1 != 0:
        raise ValidationError("Selling price must be a whole shilling amount.")

    amount_paid = int(amount_paid or 0)
    amount_received = int(amount_received or 0)
    if amount_paid < 0:
        raise ValidationError("Amount paid cannot be negative.")
    if amount_paid > int(price):
        raise ValidationError("Amount paid cannot exceed the selling price.")
    balance = int(price) - amount_paid
    if balance > 0 and customer is None:
        raise ValidationError("A customer must be selected for sales with a due balance.")
    if amount_paid > 0 and payment_method is None:
        raise ValidationError("A payment method is required when an amount is paid.")

    with transaction.atomic():
        sale = Sales.objects.create(
            store=store,
            customer=customer,
            total_amount=int(price),
            amount_paid=amount_paid,
            balance=balance,
            amount_received=amount_received,
            change=max(0, amount_received - amount_paid),
            payment_method=payment_method,
            note=note,
            recorded_by=user,
        )

        # Locks are always taken in product-pk order to avoid deadlocks
        # between concurrent mixture sales sharing components.
        normalized.sort(key=lambda pair: pair[0].pk)

        line = PerfumeSaleLine.objects.create(
            sale=sale,
            total_quantity_ml=total_ml,
            selling_price=price,
            total_cost=Decimal('0'),
            note=note,
        )

        total_cost = Decimal('0')
        for product, qty in normalized:
            unit_price_row = get_ml_unit_price(product)
            if unit_price_row is None:
                raise ValidationError(
                    f"{product.name} has no millilitre unit configured. "
                    f"Add an 'ml' unit price for this product first."
                )
            # Same conversion machinery as the rest of the system. Raises a
            # clear ValidationError if the conversion yields fractional units.
            base_quantity = convert_to_base_units(
                product, unit_price_row.unit, int(qty)
            )
            component_cost = _consume_stock_fifo(
                sale, product, base_quantity, user
            )
            PerfumeSaleComponent.objects.create(
                line=line,
                product=product,
                quantity_ml=qty,
                base_quantity=base_quantity,
                unit_cost=(component_cost / Decimal(base_quantity)).quantize(
                    Decimal('0.0001')
                ) if base_quantity else Decimal('0'),
                component_cost=component_cost,
            )
            total_cost += component_cost

        line.total_cost = total_cost
        line.save(update_fields=['total_cost'])

        # Mirror the ordinary POS flow: record a Payment so the customer
        # ledger and balances stay consistent (a signal creates the ledger
        # entry).
        if amount_paid > 0 and payment_method and customer:
            Payment.objects.create(
                customer=customer,
                amount=amount_paid,
                payment_method=payment_method,
                reference=sale.receipt_no,
                note=f"Payment for sale {sale.receipt_no}",
                payment_date=timezone.now(),
            )

    return sale
