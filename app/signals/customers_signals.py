from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from app.models.customers import Payment, CustomerLedger
from app.models.transactions import Sales
from django.db.models import Sum

def update_customer_balance(customer):
    result = customer.ledger_entries.aggregate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    )
    total_debit = result['total_debit'] or 0
    total_credit = result['total_credit'] or 0
    customer.balance = total_debit - total_credit
    customer.save(update_fields=['balance'])

# Create ledger entry when a Payment is created
@receiver(post_save, sender=Payment)
def create_ledger_on_payment(sender, instance, created, **kwargs):
    if created:
        CustomerLedger.objects.create(
            customer=instance.customer,
            transaction_type='PAYMENT',
            description=f'Payment received (Ref: {instance.reference})',
            debit=0,
            credit=instance.amount,
            note=instance.note or '',
        )
    update_customer_balance(instance.customer)

# Delete ledger entry if Payment is deleted
@receiver(post_delete, sender=Payment)
def delete_ledger_on_payment_delete(sender, instance, **kwargs):
    CustomerLedger.objects.filter(
        customer=instance.customer,
        transaction_type='PAYMENT',
        credit=instance.amount,
        note=instance.note or ''
    ).delete()
    update_customer_balance(instance.customer)



# Create ledger entry when a Sale is created 
@receiver(post_save, sender=Sales)
def create_ledger_on_sale(sender, instance, created, **kwargs):
    if created and instance.customer and not instance.is_cancelled:
        # Only create on initial creation
        CustomerLedger.objects.create(
            customer=instance.customer,
            transaction_type='SALE',
            description=f'Sale (Receipt: {instance.receipt_no})',
            debit=instance.total_amount,
            credit=0,
            note=instance.note or '',
        )
    
    # Always update balance (even on updates)
    if instance.customer:
        update_customer_balance(instance.customer)
        
        
        
        

# Delete ledger entry if Sale is deleted
@receiver(post_delete, sender=Sales)
def delete_ledger_on_sale_delete(sender, instance, **kwargs):
    if instance.customer:
        # Delete by receipt number, not by balance (which changes!)
        CustomerLedger.objects.filter(
            customer=instance.customer,
            transaction_type='SALE',
            description__contains=instance.receipt_no
        ).delete()
        update_customer_balance(instance.customer)
