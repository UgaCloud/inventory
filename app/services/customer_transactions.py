from django.db import transaction
from app.models.transactions import Sales
from app.models.customers import Payment, CustomerLedger

def record_sale_and_payment(customer, total_amount, amount_paid, sale_instance=None, note=None):
    """
    Create or update a sale for a customer, handling partial/zero balance and ledger entries.
    Returns the sale instance.
    """
    with transaction.atomic():
        balance = total_amount - amount_paid
        if sale_instance is None:
            sale = Sales.objects.create(
                customer=customer,
                total_amount=total_amount,
                amount_paid=amount_paid,
                balance=balance,
                note=note or '',
                status='Pending' if balance > 0 else 'Fulfilled',
            )
        else:
            sale = sale_instance
            sale.total_amount = total_amount
            sale.amount_paid = amount_paid
            sale.balance = balance
            sale.note = note or ''
            sale.status = 'Pending' if balance > 0 else 'Fulfilled'
            sale.save()
        # Ledger: record debit for balance (if any)
        if balance > 0:
            CustomerLedger.objects.create(
                customer=customer,
                transaction_type='SALE',
                description=f'Sale (Receipt: {getattr(sale, "receipt_no", "-")})',
                debit=balance,
                credit=0,
                note=note or ''
            )
        # Ledger: record credit for payment (if any)
        if amount_paid > 0:
            payment = Payment.objects.create(
                customer=customer,
                amount=amount_paid,
                note=note or ''
            )
            CustomerLedger.objects.create(
                customer=customer,
                transaction_type='PAYMENT',
                description=f'Payment for sale (Receipt: {getattr(sale, "receipt_no", "-")})',
                debit=0,
                credit=amount_paid,
                note=note or ''
            )
        return sale
