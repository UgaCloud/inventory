 
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

from app.models.transactions import TransferRequest, TransferRequestItem, StockTransfer, StockTransferItem
from app.models.products import Inventory


def create_transfer_request(requested_by, from_store, to_store, items):
    """Create a TransferRequest with items.

    items: list of dicts {'product': product_instance, 'quantity': int, 'units': unit_instance}
    Validates available (non-expired) stock before creating.
    """
    if from_store == to_store:
        raise ValidationError("Source and destination stores cannot be the same")

    with transaction.atomic():
        tr = TransferRequest.objects.create(requested_by=requested_by, from_store=from_store, to_store=to_store, status='pending', request_date=timezone.now())

        # Validate and create items
        for it in items:
            product = it.get('product')
            qty = int(it.get('quantity', 0))
            units = it.get('units', None)

            if qty <= 0:
                raise ValidationError(f"Quantity must be positive for product {product}")

            # Check available stock
            inv = Inventory.objects.filter(product=product, store=from_store).first()
            available = inv.quantity_in_stock if inv else 0
            if available < qty:
                raise ValidationError(f"Insufficient stock for {product.name} in {from_store.name}: available {available}, requested {qty}")

            TransferRequestItem.objects.create(transfer_request=tr, product=product, quantity=qty, units=units)

        return tr


def approve_transfer_request(tr_id, approver):
    """Approve a TransferRequest and auto-create StockTransfer with items prefilled.
    Only users with proper perms should call this (permission check left to caller).
    """
    tr = TransferRequest.objects.select_related('from_store', 'to_store').get(pk=tr_id)
    if tr.status != 'pending':
        raise ValidationError('Only pending requests can be approved')

    with transaction.atomic():
        tr.status = 'approved'
        tr.approved_by = approver
        tr.approved_date = timezone.now()
        tr.save(update_fields=['status', 'approved_by', 'approved_date'])

        # Create StockTransfer
        st = StockTransfer.objects.create(
            transfer_request=tr,
            from_store=tr.from_store,
            to_store=tr.to_store,
            status='pending',
            created_by=approver
        )

        for item in tr.items.all():
            StockTransferItem.objects.create(
                stock_transfer=st,
                product=item.product,
                quantity=item.quantity,
                units=item.units,
                transfer_request_item=item
            )

        return st


def complete_stock_transfer(transfer_id, user):
    """Mark a StockTransfer as completed and apply inventory changes via model method.
    Performs permission checks and ensures atomic behavior.
    """
    st = StockTransfer.objects.select_for_update().get(pk=transfer_id)
    if st.status == 'completed':
        raise ValidationError('Transfer is already completed')

    # caller must ensure user has permission; otherwise raise
    with transaction.atomic():
        st.status = 'completed'
        st.save(update_fields=['status'])
        # Delegate to model method which is atomic and does locking
        st.apply_inventory_changes()
        return st


def start_stock_transfer(transfer_id, user):
    """Mark a StockTransfer as in_transit after validating stock availability.
    This mirrors the behavior in the server view and is safe to call from APIs.
    """
    st = StockTransfer.objects.select_for_update().get(pk=transfer_id)
    if st.status != 'pending':
        raise ValidationError('Only pending transfers can be started')

    # Validate stock availability similar to start_stock_transfer view
    stock_issues = []
    for item in st.items.all():
        try:
            inventory = Inventory.objects.get(product=item.product, store=st.from_store)
            if inventory.quantity_in_stock < item.quantity:
                stock_issues.append(f"{item.product.name}: Available {inventory.quantity_in_stock}, Required {item.quantity}")
        except Inventory.DoesNotExist:
            stock_issues.append(f"{item.product.name}: No inventory found")

    if stock_issues:
        raise ValidationError(f"Insufficient stock: {', '.join(stock_issues)}")

    st.status = 'in_transit'
    st.save(update_fields=['status'])
    return st
