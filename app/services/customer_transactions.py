from django.db import transaction
from app.models.transactions import Sales
from app.models.customers import Payment, CustomerLedger

def record_sale_and_payment(receipt_no, store, customer, total_amount, amount_paid, amount_received, change, payment_method, sale_instance=None, note=None):
    """
    Create or update a sale for a customer, handling partial/zero balance and ledger entries.
    Returns the sale instance.
    """
    with transaction.atomic():
        balance = total_amount - amount_paid
        if sale_instance is None:
            sale = Sales.objects.create(
                receipt_no=receipt_no,
                store=store,
                customer=customer,
                amount_paid=amount_paid,
                balance=balance,
                payment_method=payment_method,
                amount_received=amount_received,
                change=change,
                note=note or '',
                status='Pending' if balance > 0 else 'Fulfilled',
            )
        else:
            sale = sale_instance
            sale.amount_paid = amount_paid
            sale.balance = balance
            sale.payment_method = payment_method
            sale.amount_received = amount_received
            sale.change = change
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
                payment_method=payment_method,
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
