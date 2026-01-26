from app.models.transactions import *
from app.models.products import *
from django.db import transaction


def return_stock_to_inventory(sale):
    """
    Return stock to inventory after sale cancellation (Simplified)
    """
    try:
        with transaction.atomic():
            for item in sale.items.all():
                # Get with lock
                inventory = Inventory.objects.select_for_update().get(
                    product=item.product,
                    store=sale.store
                )
                
                # Simple arithmetic - no F() expressions
                new_quantity = inventory.quantity_in_stock + item.base_quantity
                inventory.quantity_in_stock = new_quantity
                inventory.save()
                
                # Create stock movement
                StockMovement.objects.create(
                    product=item.product,
                    store=sale.store,
                    transaction_type='CANCELLATION',
                    quantity=item.base_quantity,
                    transaction_id=sale.id,
                    note=f"Cancelled sale {sale.receipt_no}",
                    units_in_stock=new_quantity,
                    user=str(sale.cancelled_by or sale.recorded_by)
                )
                
                # Simple batch return
                InventoryBatch.objects.create(
                    product=item.product,
                    store=sale.store,
                    quantity=item.base_quantity,
                    remaining_quantity=item.base_quantity,
                    unit_cost=0,  # Unknown cost for returns
                    expiry_date=None,
                    purchase_order_item=None
                )
                
                item.is_cancelled = True
                item.save()
                
        return True
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




