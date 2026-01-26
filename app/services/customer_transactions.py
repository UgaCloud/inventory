from django.db import transaction
from app.models.transactions import Sales
from app.models.customers import Payment, CustomerLedger, PaymentAllocation
from app.models.customers import Customer
from decimal import Decimal

def record_sale_and_payment(receipt_no, store, customer, total_amount, amount_paid, amount_received, change, payment_method, user, sale_instance=None, note=None):
    """
    Create or update a sale for a customer, handling partial/zero balance and ledger entries.
    Returns the sale instance.
    """
    with transaction.atomic():
        # Ensure numeric types are Decimal for consistent arithmetic
        total_amount = Decimal(total_amount)
        amount_paid = Decimal(amount_paid)
        # Lock customer row to avoid race conditions
        db_customer = Customer.objects.select_for_update().get(pk=customer.pk)

        new_balance = total_amount - amount_paid

        if sale_instance is None:
            sale = Sales.objects.create(
                receipt_no=receipt_no,
                store=store,
                customer=db_customer,
                amount_paid=amount_paid,
                balance=new_balance,
                payment_method=payment_method,
                amount_received=amount_received,
                change=change,
                note=note or '',
                status='Pending' if new_balance > 0 else 'Fulfilled',
                recorded_by=user
            )
            # New sale increases customer balance by the unpaid amount (total - paid)
            if new_balance != Decimal('0'):
                db_customer.balance = (db_customer.balance or Decimal('0')) + new_balance
                db_customer.save(update_fields=['balance'])
        else:
            # Updating existing sale: adjust customer balance by the difference
            sale = sale_instance
            # load fresh values in case the instance is stale
            sale.refresh_from_db()
            old_balance = Decimal(sale.balance or 0)
            old_amount_paid = Decimal(sale.amount_paid or 0)

            sale.amount_paid = amount_paid
            sale.balance = new_balance
            sale.payment_method = payment_method
            sale.amount_received = amount_received
            sale.change = change
            sale.note = note or ''
            sale.status = 'Pending' if new_balance > 0 else 'Fulfilled'
            sale.save()

            # Adjust customer balance by delta
            delta = new_balance - old_balance
            if delta != Decimal('0'):
                db_customer.balance = (db_customer.balance or Decimal('0')) + delta
                db_customer.save(update_fields=['balance'])

        # Ledger: record credit for payment (if any); create Payment record
        # The signal will automatically create the ledger entry when Payment is created
        if amount_paid > 0:
            payment = Payment.objects.create(
                customer=db_customer,
                amount=amount_paid,
                payment_method=payment_method,
                note=note or ''
            )
            # Signal will automatically create ledger entry - NO MANUAL CREATION

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
        # Lock customer row for update
        db_customer = Customer.objects.select_for_update().get(pk=customer.pk)
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
        # Signal will automatically create ledger entry - NO MANUAL CREATION
        
        # Reduce customer outstanding balance by the payment amount
        db_customer.balance = (db_customer.balance or Decimal('0')) - Decimal(payment_amount)
        db_customer.save(update_fields=['balance'])
    return payment