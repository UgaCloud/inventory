from django.db import models
from datetime import date, timedelta

from app.constants import CASHFLOW_TYPES, TRANSACTION_TYPES

class CashFlow(models.Model):
    store = models.ForeignKey('app.StoreLocation', on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    transaction_type = models.CharField(max_length=20, choices=CASHFLOW_TYPES)
    reference = models.CharField(max_length=100, blank=True, null=True)
    user = models.CharField(max_length=50)
    note = models.TextField(blank=True, null=True)
    payment_method = models.ForeignKey('app.PaymentMethod', on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def is_inflow(self):
        return self.amount > 0

    @property
    def is_outflow(self):
        return self.amount < 0

    @property
    def abs_amount(self):
        return abs(self.amount)

    def __str__(self):
        return f"CashFlow: {self.get_transaction_type_display()} {self.amount} on {self.date} ({self.store})"

class DailyCashSummary(models.Model):
    store = models.ForeignKey('app.StoreLocation', on_delete=models.CASCADE)
    date = models.DateField()
    opening_balance = models.DecimalField(max_digits=12, decimal_places=0)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=0)
    calculated_balance = models.DecimalField(max_digits=12, decimal_places=0)
    note = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ("store", "date")

    @property
    def net_flow(self):
        return self.closing_balance - self.opening_balance

    @property
    def discrepancy(self):
        return self.closing_balance - self.calculated_balance

    def __str__(self):
        return f"DailyCashSummary: {self.store} {self.date} | Opening: {self.opening_balance} | Closing: {self.closing_balance}"

class BankAccount(models.Model):
    name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50, unique=True)
    bank_name = models.CharField(max_length=100)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=0,  default=0)
    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.bank_name} - {self.account_number} ({self.name})"

class BankTransaction(models.Model):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='transactions')
    store = models.ForeignKey('app.StoreLocation', on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    reference = models.CharField(max_length=100, blank=True, null=True)
    user = models.CharField(max_length=50)
    note = models.TextField(blank=True, null=True)
    related_cashflow = models.ForeignKey('CashFlow', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_transactions')

    @property
    def is_inflow(self):
        return self.amount > 0

    @property
    def is_outflow(self):
        return self.amount < 0

    @property
    def abs_amount(self):
        return abs(self.amount)

    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.amount} on {self.date} ({self.bank_account})"

class PaymentMethod(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name


