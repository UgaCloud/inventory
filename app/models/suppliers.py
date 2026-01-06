from django.db import models


# app/models/__init__.py or create supplier.py
from django.db import models

class Supplier(models.Model):
    name = models.CharField(max_length=255, unique=True)
    supplier_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    payment_terms = models.CharField(max_length=50, default='Net 30')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'

    def __str__(self):
        return f"{self.name} ({self.supplier_code})"

    def save(self, *args, **kwargs):
        if not self.supplier_code:
            # Auto-generate supplier code
            prefix = 'SUP'
            last_supplier = Supplier.objects.filter(supplier_code__startswith=prefix).order_by('supplier_code').last()
            if last_supplier and last_supplier.supplier_code:
                try:
                    last_num = int(last_supplier.supplier_code.split('-')[1])
                    next_num = last_num + 1
                except (IndexError, ValueError):
                    next_num = 1
            else:
                next_num = 1
            self.supplier_code = f"{prefix}-{next_num:03d}"
        super().save(*args, **kwargs)
