from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from app.models.expense import Expense
from app.models.finance import CashFlow

@receiver(post_save, sender=Expense)
def create_or_update_cashflow_for_expense(sender, instance, created, **kwargs):
    if created and not instance.related_cashflow:
        with transaction.atomic():
            cashflow = CashFlow.objects.create(
                store=instance.store,
                amount=-instance.amount,  
                transaction_type='EXPENSE',
                reference=instance.reference,
                user=instance.user,
                note=f"Expense: {instance.description or ''}",
                payment_method=getattr(instance, 'payment_method', None)
            )
            instance.related_cashflow = cashflow
            instance.save(update_fields=["related_cashflow"])
    elif not created and instance.related_cashflow:
        with transaction.atomic():
            cashflow = instance.related_cashflow
            cashflow.store = instance.store
            cashflow.amount = -instance.amount
            cashflow.transaction_type = 'EXPENSE'
            cashflow.reference = instance.reference
            cashflow.user = instance.user
            cashflow.note = f"Expense: {instance.description or ''}"
            cashflow.payment_method = getattr(instance, 'payment_method', None)
            cashflow.save()

@receiver(post_delete, sender=Expense)
def delete_cashflow_for_expense(sender, instance, **kwargs):
    if instance.related_cashflow:
        with transaction.atomic():
            instance.related_cashflow.delete()
