from django.db.models.signals import post_save
from django.dispatch import receiver
from app.models.transactions import StockTransferItem

@receiver(post_save, sender=StockTransferItem)
def handle_fifo_transfer(sender, instance, created, **kwargs):
    if created:
        instance.apply_fifo_transfer()
