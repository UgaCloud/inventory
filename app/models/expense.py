from django.db import models

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Expense(models.Model):
    store = models.ForeignKey('app.StoreLocation', on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    user = models.CharField(max_length=50)
    related_purchase = models.ForeignKey('app.PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    related_sale = models.ForeignKey('app.Sales', on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    related_cashflow = models.ForeignKey('app.CashFlow', on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    attachment = models.FileField(upload_to='expense_attachments/', null=True, blank=True)
    payment_method = models.ForeignKey('app.PaymentMethod', on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')

    def __str__(self):
        return f"{self.category} - {self.amount} on {self.date} ({self.store})"

    @property
    def is_linked_to_purchase(self):
        return self.related_purchase is not None

    @property
    def is_linked_to_sale(self):
        return self.related_sale is not None

    @property
    def is_linked_to_cashflow(self):
        return self.related_cashflow is not None

    @property
    def abs_amount(self):
        return abs(self.amount)
