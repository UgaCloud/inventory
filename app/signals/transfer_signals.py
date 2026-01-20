"""
Real-time stock deduction signals for stock transfers.
Deducts stock from source store when transfers are created/items added.
Adds stock to destination when transfers are completed.
Reverses deductions when transfers are cancelled.
"""
from django.db import transaction
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError
from app.models.transactions import StockTransfer, StockTransferItem, StockMovement
from app.models.products import Inventory


@receiver(pre_save, sender=StockTransfer)
def store_transfer_status(sender, instance, **kwargs):
    """Store old status before save to detect status changes"""
    if instance.pk:
        try:
            old_instance = StockTransfer.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except StockTransfer.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


# @receiver(post_save, sender=StockTransfer)
# def handle_transfer_status_change(sender, instance, created, **kwargs):
#     """
#     Handle stock deductions/additions based on transfer status changes.
#     - pending/in_transit: Deduct from source store (reserve stock)
#     - completed: Stock already moved by apply_inventory_changes()
#     - cancelled: Reverse deductions
#     """
#     if created:
#         # New transfer - deduct stock from source store for all items
#         _deduct_stock_for_transfer(instance)
#     else:
#         # Status change
#         old_status = getattr(instance, '_old_status', None)
#         new_status = instance.status
        
#         if old_status != new_status:
#             if new_status == 'cancelled':
#                 # Reverse all deductions
#                 _reverse_stock_deductions(instance)
#             elif new_status == 'completed':
#                 # Stock movement handled by apply_inventory_changes()
#                 # But we need to ensure source deductions are still in place
#                 pass
#             elif new_status in ['pending', 'in_transit'] and old_status not in ['pending', 'in_transit']:
#                 # Re-activate transfer (e.g., from cancelled)
#                 _deduct_stock_for_transfer(instance)


# @receiver(post_save, sender=StockTransferItem)
# def handle_transfer_item_stock(sender, instance, created, **kwargs):
#     """
#     Deduct stock from source store when transfer items are added/updated.
#     Only deducts if transfer is in pending/in_transit status.
#     """
#     transfer = instance.stock_transfer
    
#     # Only process if transfer is active (not completed or cancelled)
#     if transfer.status in ['pending', 'in_transit']:
#         if created:
#             # New item added - deduct stock
#             _deduct_stock_for_item(instance, transfer.created_by)
#         else:
#             # Item updated - adjust stock difference
#             if hasattr(instance, '_old_quantity'):
#                 old_qty = instance._old_quantity
#                 new_qty = instance.quantity
#                 if old_qty != new_qty:
#                     diff = new_qty - old_qty
#                     if diff > 0:
#                         # Quantity increased - deduct more
#                         _deduct_stock_quantity(
#                             transfer.from_store,
#                             instance.product,
#                             diff,
#                             transfer.id,
#                             f"Transfer #{transfer.id} item quantity increased",
#                             user=transfer.created_by
#                         )
#                     elif diff < 0:
#                         # Quantity decreased - reverse some
#                         _add_stock_quantity(
#                             transfer.from_store,
#                             instance.product,
#                             abs(diff),
#                             transfer.id,
#                             f"Transfer #{transfer.id} item quantity decreased",
#                             user=transfer.created_by
#                         )


@receiver(pre_save, sender=StockTransferItem)
def store_item_quantity(sender, instance, **kwargs):
    """Store old quantity before save to detect quantity changes"""
    if instance.pk:
        try:
            old_instance = StockTransferItem.objects.get(pk=instance.pk)
            instance._old_quantity = old_instance.quantity
        except StockTransferItem.DoesNotExist:
            instance._old_quantity = 0
    else:
        instance._old_quantity = 0


@receiver(post_delete, sender=StockTransferItem)
def handle_transfer_item_deletion(sender, instance, **kwargs):
    """
    Reverse stock deduction when transfer items are deleted.
    Only if transfer is still pending/in_transit.
    """
    transfer = instance.stock_transfer
    
    if transfer and transfer.status in ['pending', 'in_transit']:
        _add_stock_quantity(
            transfer.from_store,
            instance.product,
            instance.quantity,
            transfer.id,
            f"Transfer #{transfer.id} item deleted - stock restored",
            user=transfer.created_by
        )


# def _deduct_stock_for_transfer(transfer):
#     """Deduct stock for all items in a transfer"""
#     if transfer.status not in ['pending', 'in_transit']:
#         return
    
#     with transaction.atomic():
#         for item in transfer.items.all():
#             _deduct_stock_for_item(item, transfer.created_by)


# def _deduct_stock_for_item(item, user=None):
#     """Deduct stock for a single transfer item"""
#     transfer = item.stock_transfer
    
#     _deduct_stock_quantity(
#         transfer.from_store,
#         item.product,
#         item.quantity,
#         transfer.id,
#         f"Transfer #{transfer.id} - {item.product.name}",
#         user=user or transfer.created_by
#     )


# def _deduct_stock_quantity(store, product, quantity, transfer_id, note, user=None):
#     """
#     Deduct stock quantity from source store.
#     Creates/updates Inventory record and logs StockMovement.
#     """
#     with transaction.atomic():
#         # Get or create inventory record
#         inventory, created = Inventory.objects.select_for_update().get_or_create(
#             store=store,
#             product=product,
#             defaults={'quantity_in_stock': 0}
#         )
        
#         # Check available stock (considering committed stock from other transfers)
#         from django.db.models import Sum
#         from app.models.transactions import StockTransferItem
        
#         # Calculate committed stock from other pending/in_transit transfers
#         committed_stock = StockTransferItem.objects.filter(
#             product=product,
#             stock_transfer__from_store=store,
#             stock_transfer__status__in=['pending', 'in_transit']
#         ).exclude(
#             stock_transfer_id=transfer_id  # Exclude current transfer
#         ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
#         available_stock = inventory.quantity_in_stock - committed_stock
        
#         if available_stock < quantity:
#             raise ValidationError(
#                 f"Insufficient stock for {product.name} in {store.name}. "
#                 f"Available: {available_stock}, Required: {quantity}"
#             )
        
#         # Deduct stock
#         inventory.quantity_in_stock = inventory.quantity_in_stock - quantity
#         inventory.save(update_fields=['quantity_in_stock'])
        
#         # Log stock movement (user defaults to 'system' if not provided)
#         username = str(user) if user else 'system'
#         StockMovement.objects.create(
#             store=store,
#             product=product,
#             transaction_type='stock_transfer_out',
#             quantity=-quantity,
#             transaction_id=transfer_id,
#             units_in_stock=inventory.quantity_in_stock,
#             note=note,
#             user=username
#         )


def _add_stock_quantity(store, product, quantity, transfer_id, note, user=None):
    """
    Add stock quantity back to source store (reverse deduction).
    Used when transfers are cancelled or items are removed.
    """
    with transaction.atomic():
        # Get or create inventory record
        inventory, created = Inventory.objects.select_for_update().get_or_create(
            store=store,
            product=product,
            defaults={'quantity_in_stock': 0}
        )
        
        # Add stock back
        inventory.quantity_in_stock = inventory.quantity_in_stock + quantity
        inventory.save(update_fields=['quantity_in_stock'])
        
        # Log stock movement (user defaults to 'system' if not provided)
        username = str(user) if user else 'system'
        StockMovement.objects.create(
            store=store,
            product=product,
            transaction_type='stock_transfer_reversal',
            quantity=quantity,
            transaction_id=transfer_id,
            units_in_stock=inventory.quantity_in_stock,
            note=note,
            user=username
        )


def _reverse_stock_deductions(transfer):
    """Reverse all stock deductions for a cancelled transfer"""
    if transfer.status != 'cancelled':
        return
    
    with transaction.atomic():
        for item in transfer.items.all():
            _add_stock_quantity(
                transfer.from_store,
                item.product,
                item.quantity,
                transfer.id,
                f"Transfer #{transfer.id} cancelled - stock restored",
                user=transfer.created_by
            )
