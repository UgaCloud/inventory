from django.db import models
from datetime import date, timedelta

from app.constants import TRANSACTION_TYPES

class CashFlow(models.Model):
    store = models.ForeignKey('app.StoreLocation', on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    reference = models.CharField(max_length=100, blank=True, null=True)
    user = models.CharField(max_length=50)
    note = models.TextField(blank=True, null=True)

    @property
    def is_inflow(self):
        return self.amount > 0

    @property
    def is_outflow(self):
        return self.amount < 0

    @property
    def abs_amount(self):
        return abs(self.amount)

class DailyCashSummary(models.Model):
    store = models.ForeignKey('app.StoreLocation', on_delete=models.CASCADE)
    date = models.DateField()
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2)
    calculated_balance = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ("store", "date")

    @property
    def net_flow(self):
        return self.closing_balance - self.opening_balance

    @property
    def discrepancy(self):
        return self.closing_balance - self.calculated_balance


