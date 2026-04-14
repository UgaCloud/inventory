from django.db import models
from django.utils import timezone

class SalesReturn(models.Model):
    sale = models.ForeignKey('app.Sales', on_delete=models.CASCADE, related_name='returns')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Return #{self.id} for Sale {self.sale.receipt_no}"
