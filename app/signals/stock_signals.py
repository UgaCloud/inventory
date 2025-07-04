from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from app.models.products import Inventory
from app.models.transactions import PurchaseOrderItem, StockMovement

@receiver(post_save, sender=PurchaseOrderItem)
def update_inventory_on_purchase(sender, instance, created, **kwargs):
    with transaction.atomic():
        if created:
            # Get or create inventory for the product and store from the purchase order
            inventory, _ = Inventory.objects.get_or_create(
                product=instance.product,
                store=instance.order.store
            )
            inventory.quantity_in_stock += instance.quantity
            inventory.save()
            # Log stock movement for creation
            StockMovement.objects.create(
                product=instance.product,
                store=instance.order.store,
                transaction_type='IN',  # Assuming 'IN' is for restock
                quantity=instance.quantity,
                transaction_id=instance.order.id,
                note='Purchase Order',
                units_in_stock=inventory.quantity_in_stock,
                user=getattr(instance.order, 'recorded_by', 'system')
            )
        else:
            # Handle update: adjust inventory by the difference in quantity
            if hasattr(instance, '_old_quantity'):
                diff = instance.quantity - instance._old_quantity
                if diff != 0:
                    inventory, _ = Inventory.objects.get_or_create(
                        product=instance.product,
                        store=instance.order.store
                    )
                    inventory.quantity_in_stock += diff
                    inventory.save()
                    
                    # Log stock movement for update
                    StockMovement.objects.create(
                        product=instance.product,
                        store=instance.order.store,
                        transaction_type='IN', 
                        quantity=diff,
                        transaction_id=instance.order.id,
                        note='Stock (update)',
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
        if inventory:
            inventory.quantity_in_stock -= instance.quantity
            inventory.save()
            
            # Log stock movement for deletion
            StockMovement.objects.create(
                product=instance.product,
                store=instance.order.store,
                transaction_type='OUT',  
                quantity=-instance.quantity,  
                transaction_id=instance.order.id,
                note='Stock (delete)',
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
