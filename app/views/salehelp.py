from app.models.transactions import *
from app.models.products import *
from django.db import transaction


def return_stock_to_inventory(sale):
    """
    Return stock to inventory after sale cancellation
    """
    try:
        with transaction.atomic():
            # Get all items in the sale
            sale_items = sale.items.all()
            
            for item in sale_items:
                product = item.product
                quantity = item.quantity
                store = sale.store
                
                # Get or create inventory record
                inventory, created = Inventory.objects.get_or_create(
                    product=product,
                    store=store,
                    defaults={'quantity_in_stock': 0}
                )
                
                # Add quantity back to inventory
                old_stock = inventory.quantity_in_stock
                inventory.quantity_in_stock = F('quantity_in_stock') + quantity
                inventory.save()
                inventory.refresh_from_db()
                
                # Create stock movement record for cancellation
                StockMovement.objects.create(
                    product=product,
                    store=store,
                    transaction_type='CANCELLATION',
                    quantity=quantity,  # Positive for addition
                    transaction_id=sale.id,
                    note=f"Sale #{sale.receipt_no} cancellation: {sale.cancellation_reason}",
                    units_in_stock=inventory.quantity_in_stock,
                    user=str(sale.cancelled_by or sale.recorded_by)
                )
                
                # Return stock to inventory batches
                return_stock_to_batches(product, store, quantity, sale)
                
                # Mark sale item as cancelled
                item.is_cancelled = True
                item.save(update_fields=['is_cancelled'])
            
    except Exception as e:
        raise Exception(f"Failed to return stock to inventory: {str(e)}")






def return_stock_to_batches(product, store, quantity_returned, sale):
    """
    Return stock to inventory batches
    """
    try:
        # First, try to add to existing batches that have remaining capacity
        existing_batches = InventoryBatch.objects.filter(
            product=product,
            store=store,
            expiry_date__isnull=False
        ).order_by('expiry_date', 'received_date')
        
        remaining_to_add = quantity_returned
        
        # Try to add to existing non-expired batches first
        for batch in existing_batches:
            if remaining_to_add <= 0:
                break
            
            if batch.expiry_date and batch.expiry_date < timezone.now().date():
                continue  # Skip expired batches
            
            # Add to this batch
            batch.remaining_quantity = F('remaining_quantity') + remaining_to_add
            batch.save()
            batch.refresh_from_db()
            remaining_to_add = 0
            break
        
        # If there's still stock to add, create new batch
        if remaining_to_add > 0:
            # Get the latest unit cost from any batch or purchase
            latest_batch = InventoryBatch.objects.filter(
                product=product,
                store=store
            ).order_by('-received_date').first()
            
            unit_cost = 0
            if latest_batch:
                unit_cost = latest_batch.unit_cost
            else:
                # Try to get from product default price
                product_obj = Product.objects.get(id=product.id)
                unit_cost = product_obj.default_price or 0
            
            # Create new batch for returned stock
            InventoryBatch.objects.create(
                product=product,
                store=store,
                quantity=remaining_to_add,
                remaining_quantity=remaining_to_add,
                unit_cost=unit_cost,
                received_date=timezone.now().date(),
                expiry_date=None,  # No expiry for returned stock
                # Note: Remove the 'note' parameter as it doesn't exist in your model
            )
                
    except Exception as e:
        raise Exception(f"Failed to return stock to batches: {str(e)}")




