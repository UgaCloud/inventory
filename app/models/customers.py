from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    company = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return self.name

class CustomerLedger(models.Model):
    TRANSACTION_TYPES = [
        ('SALE', 'Sale'),
        ('PAYMENT', 'Payment'),
        ('REFUND', 'Refund'),
        ('ADJUSTMENT', 'Adjustment'),
    ]
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='ledger_entries')
    date = models.DateTimeField(auto_now_add=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.CharField(max_length=255, blank=True, null=True)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)   
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0) 
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Customer Ledger Entry'
        verbose_name_plural = 'Customer Ledger Entries'

    def __str__(self):
        return f"{self.customer.name} | {self.date.date()} | {self.transaction_type} | Debit: {self.debit} | Credit: {self.credit}"

class Payment(models.Model):
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.ForeignKey('app.PaymentMethod', on_delete=models.RESTRICT)
    reference = models.CharField(max_length=100, blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"{self.customer.name} | {self.amount} | {self.payment_date.date()}"

class PaymentAllocation(models.Model):
    payment = models.ForeignKey('Payment', on_delete=models.CASCADE, related_name='allocations')
    sale = models.ForeignKey('app.Sales', on_delete=models.CASCADE, related_name='payment_allocations')
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Payment Allocation'
        verbose_name_plural = 'Payment Allocations'

    def __str__(self):
        return f"{self.payment} -> {self.sale} | {self.amount}"




