from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from app.models.transactions import SalesItem
from app.models.products import Inventory, ProductUnitPrice
from app.models.transactions import StockMovement
from app.models.transactions import InventoryBatch

@receiver(post_save, sender=SalesItem)
def update_inventory_on_sale(sender, instance, created, **kwargs):
    with transaction.atomic():
        unit_price = ProductUnitPrice.objects.filter(product=instance.product, unit=instance.unit).first()
        
        conversion_factor = unit_price.conversion_factor if unit_price else 1.0
        
        inventory, _ = Inventory.objects.get_or_create(
            product=instance.product,
            store=instance.order.store
        )
        
        quantity_base = instance.quantity * conversion_factor
        
        if created:
            # FIFO: Deduct from oldest batches first
            batches = InventoryBatch.objects.filter(product=instance.product, store=instance.order.store, remaining_quantity__gt=0).order_by('received_date')
            
            to_deduct = quantity_base
            
            for batch in batches:
                if batch.remaining_quantity >= to_deduct:
                    batch.remaining_quantity -= to_deduct
                    batch.save()
                    break
                else:
                    to_deduct -= batch.remaining_quantity
                    batch.remaining_quantity = 0
                    batch.save()
            
            inventory.quantity_in_stock -= quantity_base
            inventory.save()
            
            StockMovement.objects.create(
                product=instance.product,
                store=instance.order.store,
                transaction_type='OUT',
                quantity=-quantity_base,
                transaction_id=instance.order.id,
                note='Sale',
                units_in_stock=inventory.quantity_in_stock,
                user=getattr(instance.order, 'recorded_by', 'system')
            )
        else:
            if hasattr(instance, '_old_quantity'):
                diff = instance.quantity - instance._old_quantity
                diff_base = diff * conversion_factor
                
                if diff_base > 0:
                    # Deduct additional quantity using FIFO
                    batches = InventoryBatch.objects.filter(product=instance.product, store=instance.order.store, remaining_quantity__gt=0).order_by('received_date')
                    
                    to_deduct = diff_base
                    
                    for batch in batches:
                        if batch.remaining_quantity >= to_deduct:
                            batch.remaining_quantity -= to_deduct
                            batch.save()
                            break
                        else:
                            to_deduct -= batch.remaining_quantity
                            batch.remaining_quantity = 0
                            batch.save()
                    
                    inventory.quantity_in_stock -= diff_base
                    inventory.save()
                    
                    StockMovement.objects.create(
                        product=instance.product,
                        store=instance.order.store,
                        transaction_type='OUT',
                        quantity=-diff_base,
                        transaction_id=instance.order.id,
                        note='Sale (update, FIFO)',
                        units_in_stock=inventory.quantity_in_stock,
                        user=getattr(instance.order, 'recorded_by', 'system')
                    )
                elif diff_base < 0:
                    # Return stock to batches (LIFO for return, but FIFO for deduction)
                    batches = InventoryBatch.objects.filter(product=instance.product, store=instance.order.store).order_by('-received_date')
                    
                    to_return = -diff_base
                    
                    for batch in batches:
                        batch.remaining_quantity += to_return
                        batch.save()
                        break
                    
                    inventory.quantity_in_stock -= diff_base
                    inventory.save()
                    
                    StockMovement.objects.create(
                        product=instance.product,
                        store=instance.order.store,
                        transaction_type='IN',
                        quantity=-diff_base,
                        transaction_id=instance.order.id,
                        note='Sale (update, return)',
                        units_in_stock=inventory.quantity_in_stock,
                        user=getattr(instance.order, 'recorded_by', 'system')
                    )

@receiver(pre_save, sender=SalesItem)
def store_old_quantity_sales(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = SalesItem.objects.get(pk=instance.pk)
            instance._old_quantity = old_instance.quantity
        except SalesItem.DoesNotExist:
            instance._old_quantity = 0
    else:
        instance._old_quantity = 0

@receiver(post_delete, sender=SalesItem)
def update_inventory_on_sale_delete(sender, instance, **kwargs):
    with transaction.atomic():
        inventory = Inventory.objects.filter(
            product=instance.product,
            store=instance.order.store
        ).first()
        
        if inventory:
            inventory.quantity_in_stock += instance.quantity
            inventory.save()
            
            StockMovement.objects.create(
                product=instance.product,
                store=instance.order.store,
                transaction_type='IN',
                quantity=instance.quantity,
                transaction_id=instance.order.id,
                note='Sale (delete)',
                units_in_stock=inventory.quantity_in_stock,
                user=getattr(instance.order, 'recorded_by', 'system')
            )
