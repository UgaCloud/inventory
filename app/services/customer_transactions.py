from django.db import transaction
from app.models.transactions import Sales
from app.models.customers import Payment, CustomerLedger, PaymentAllocation

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

def allocate_bulk_payment_to_sales(customer, payment_amount, payment_method, reference='', note=''):
    """
    Allocates a payment to the customer's oldest outstanding sales (receipts),
    updates balances/statuses, creates Payment, ledger entry, and PaymentAllocation records.
    Returns the Payment instance.
    """
    with transaction.atomic():
        sales = Sales.objects.filter(
            customer=customer,
        ).exclude(balance=0).order_by('sale_date', 'id')

        remaining = payment_amount
        allocations = []
        payment = None
        for sale in sales:
            if remaining <= 0:
                break
            to_pay = min(sale.balance, remaining)
            sale.amount_paid += to_pay
            sale.balance -= to_pay
            if sale.balance <= 0:
                sale.status = 'FULFILLED'
                sale.balance = 0
            else:
                sale.status = 'PARTIALLY_PAID'
            sale.save(update_fields=['amount_paid', 'balance', 'status'])
            remaining -= to_pay
            # Create payment if not already created
            if payment is None:
                payment = Payment.objects.create(
                    customer=customer,
                    amount=payment_amount,
                    payment_method=payment_method,
                    reference=reference,
                    note=note,
                )
            # Save allocation
            PaymentAllocation.objects.create(payment=payment, sale=sale, amount=to_pay)
            allocations.append((sale, to_pay))
        # If payment was not created (no sales to allocate), still create payment record
        if payment is None:
            payment = Payment.objects.create(
                customer=customer,
                amount=payment_amount,
                payment_method=payment_method,
                reference=reference,
                note=note,
            )
        CustomerLedger.objects.create(
            customer=customer,
            transaction_type='PAYMENT',
            description=f'Bulk payment allocation',
            debit=0,
            credit=payment_amount,
            note=note,
        )
    return payment
