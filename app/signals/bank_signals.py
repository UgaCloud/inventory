from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from app.models.finance import BankTransaction, CashFlow

@receiver(post_save, sender=BankTransaction)
def create_cashflow_for_bank_transaction(sender, instance, created, **kwargs):
    if created and not instance.related_cashflow:
        with transaction.atomic():
            # Only create a CashFlow if not already linked
            cashflow = CashFlow.objects.create(
                store=instance.store,
                amount=instance.amount,
                transaction_type=instance.transaction_type,
                reference=instance.reference,
                user=instance.user,
                note=f"Bank transaction: {instance.note or ''}"
            )
            instance.related_cashflow = cashflow
            instance.save(update_fields=["related_cashflow"])
