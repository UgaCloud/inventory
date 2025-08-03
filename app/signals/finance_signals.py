from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from app.models.transactions import Sales, PurchaseOrder
from app.models.finance import CashFlow

@receiver(post_save, sender=Sales)
def create_cash_flow_on_sale(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            CashFlow.objects.create(
                store=instance.store,
                amount=instance.total_amount,
                transaction_type='SALE',
                reference=instance.receipt_no,
                user=instance.recorded_by,
                note=f"Sale: {instance.note or ''}",
                payment_method=getattr(instance, 'payment_method', None)
            )

@receiver(post_save, sender=PurchaseOrder)
def create_cash_flow_on_purchase(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            CashFlow.objects.create(
                store=instance.store,
                amount=-instance.total_cost,  # Outflow
                transaction_type='PURCHASE',
                reference=f'PO-{instance.id}',
                user=instance.recorded_by,
                note=f"Purchase: {instance.note or ''}",
                payment_method=getattr(instance, 'payment_method', None)
            )
