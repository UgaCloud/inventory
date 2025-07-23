from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from app.models.products import Inventory, ProductUnitPrice
from app.models.transactions import PurchaseOrderItem, StockMovement, InventoryBatch
from datetime import date

@receiver(post_save, sender=PurchaseOrderItem)
def update_inventory_on_purchase(sender, instance, created, **kwargs):
    with transaction.atomic():
        unit_price = ProductUnitPrice.objects.filter(product=instance.product, unit=instance.unit).first()
        
        conversion_factor = unit_price.conversion_factor if unit_price else 1.0
        
        quantity_base = instance.quantity * conversion_factor
        
        if created:
            inventory, _ = Inventory.objects.get_or_create(
                product=instance.product,
                store=instance.order.store
            )
            
            inventory.quantity_in_stock += quantity_base
            inventory.save()
            
            # Create a new batch for FIFO
            InventoryBatch.objects.create(
                product=instance.product,
                store=instance.order.store,
                quantity=quantity_base,
                unit_cost=instance.unit_cost,
                remaining_quantity=quantity_base,
                purchase_order_item=instance,
                expiry_date=instance.expiry_date  # Pass expiry from PurchaseOrderItem
            
            )

            # Log stock movement
            StockMovement.objects.create(
                product=instance.product,
                store=instance.order.store,
                transaction_type='IN',
                quantity=quantity_base,
                transaction_id=instance.order.id,
                note='Purchase Order',
                units_in_stock=inventory.quantity_in_stock,
                user=getattr(instance.order, 'recorded_by', 'system')
            )
        else:
            if hasattr(instance, '_old_quantity'):
                diff = instance.quantity - instance._old_quantity
                diff_base = diff * conversion_factor
                
                if diff > 0:
                    inventory, _ = Inventory.objects.get_or_create(
                        product=instance.product,
                        store=instance.order.store
                    )
                    
                    inventory.quantity_in_stock += diff_base
                    inventory.save()
                    
                    # Add new batch for increased quantity
                    InventoryBatch.objects.create(
                        product=instance.product,
                        store=instance.order.store,
                        quantity=diff_base,
                        unit_cost=instance.unit_cost,
                        remaining_quantity=diff_base,
                        purchase_order_item=instance,
                        expiry_date=instance.expiry_date  # Pass expiry from PurchaseOrderItem
                    )

                    # Log stock movement for increase
                    StockMovement.objects.create(
                        product=instance.product,
                        store=instance.order.store,
                        transaction_type='IN', 
                        quantity=diff_base,
                        transaction_id=instance.order.id,
                        note='Stock (update)',
                        units_in_stock=inventory.quantity_in_stock,
                        user=getattr(instance.order, 'recorded_by', 'system')
                    )
                elif diff < 0:
                    # Remove from batches (LIFO for removal, but FIFO for deduction)
                    batches = InventoryBatch.objects.filter(product=instance.product, store=instance.order.store, remaining_quantity__gt=0).order_by('received_date')
                    
                    to_remove = -diff_base
                    
                    for batch in batches:
                        if batch.remaining_quantity >= to_remove:
                            batch.remaining_quantity -= to_remove
                            batch.save()
                            break
                        else:
                            to_remove -= batch.remaining_quantity
                            batch.remaining_quantity = 0
                            batch.save()
                    
                    inventory, _ = Inventory.objects.get_or_create(
                        product=instance.product,
                        store=instance.order.store
                    )
                    
                    inventory.quantity_in_stock += diff_base
                    inventory.save()
                    
                    StockMovement.objects.create(
                        product=instance.product,
                        store=instance.order.store,
                        transaction_type='OUT', 
                        quantity=diff_base,
                        transaction_id=instance.order.id,
                        note='Stock (update, reduce)',
                        units_in_stock=inventory.quantity_in_stock,
                        user=getattr(instance.order, 'recorded_by', 'system')
                    )

@receiver(pre_save, sender=PurchaseOrderItem)
def store_old_quantity(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = PurchaseOrderItem.objects.get(pk=instance.pk)
            instance._old_quantity = old_instance.quantity
        except PurchaseOrderItem.DoesNotExist:
            instance._old_quantity = 0
    else:
        instance._old_quantity = 0

@receiver(post_delete, sender=PurchaseOrderItem)
def update_inventory_on_purchase_delete(sender, instance, **kwargs):
    with transaction.atomic():
        inventory = Inventory.objects.filter(
            product=instance.product,
            store=instance.order.store
        ).first()
        unit_price = ProductUnitPrice.objects.filter(product=instance.product, unit=instance.unit).first()
        conversion_factor = unit_price.conversion_factor if unit_price else 1.0
        quantity_base = instance.quantity * conversion_factor
        if inventory:
            inventory.quantity_in_stock -= quantity_base
            inventory.save()
            # Remove from batches (FIFO: oldest, non-expired first)
            batches = InventoryBatch.objects.filter(
                product=instance.product,
                store=instance.order.store,
                remaining_quantity__gt=0,
                expiry_date__gte=date.today()
            ).order_by('expiry_date', 'received_date')
            to_remove = quantity_base
            for batch in batches:
                if batch.remaining_quantity >= to_remove:
                    batch.remaining_quantity -= to_remove
                    batch.save()
                    break
                else:
                    to_remove -= batch.remaining_quantity
                    batch.remaining_quantity = 0
                    batch.save()
            StockMovement.objects.create(
                product=instance.product,
                store=instance.order.store,
                transaction_type='OUT',
                quantity=-quantity_base,
                transaction_id=instance.order.id,
                note='Purchase Order Item deleted',
                units_in_stock=inventory.quantity_in_stock,
                user=getattr(instance.order, 'recorded_by', 'system')
            )

@receiver(post_save, sender=Inventory)
def log_stockmovement_on_inventory_insert_update(sender, instance, created, **kwargs):
    with transaction.atomic():
        if created:
            StockMovement.objects.create(
                product=instance.product,
                store=instance.store,
                transaction_type='Initial Stock',
                quantity=instance.quantity_in_stock,
                transaction_id=None,
                note='Inventory created',
                units_in_stock=instance.quantity_in_stock,
                user='system'
            )

@receiver(post_delete, sender=Inventory)
def log_stockmovement_on_inventory_delete(sender, instance, **kwargs):
    with transaction.atomic():
        StockMovement.objects.create(
            product=instance.product,
            store=instance.store,
            transaction_type='Removed',
            quantity=-instance.quantity_in_stock,
            transaction_id=None,
            note='Inventory deleted',
            units_in_stock=0,
            user='system'
        )
