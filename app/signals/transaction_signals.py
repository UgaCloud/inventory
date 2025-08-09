from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from app.models.transactions import PurchaseOrderItem, PurchaseOrder, SalesItem, Sales

@receiver([post_save, post_delete], sender=PurchaseOrderItem)
def update_purchase_order_total_cost(sender, instance, **kwargs):
    if instance.order:
        instance.order.update_total_cost()

@receiver([post_save, post_delete], sender=SalesItem)
def update_sales_total_amount(sender, instance, **kwargs):
    if instance.order:
        instance.order.update_total_amount()
