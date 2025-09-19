from django.db import models
import uuid
from app.models.organization import Branch
import re


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
    
    @property
    def no_of_products(self):
        return self.products.count()


class UnitOfMeasure(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g., "Kilogram"
    abbreviation = models.CharField(max_length=10)        # e.g., "kg"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True, blank=True)  
    brand = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True)
    uuid_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.brand})"

    @property
    def total_stock(self): # Total units across all stores
        return sum(item.quantity_in_stock for item in self.inventories.all())

    def default_unit(self):
        unit = self.unit_prices.order_by('id').first()
        return unit if unit else "Piece"
    
    @property
    def default_price(self):
        unit = self.unit_prices.order_by('id').first()
        return unit.price if unit else 0

    @property
    def total_sales_quantity(self): # All sales across orders
        return sum(item.quantity for item in self.salesorderitem_set.all())

    @property
    def total_purchase_quantity(self): # All purchases across orders
        return sum(item.quantity for item in self.purchaseorderitem_set.all())

    def save(self, *args, **kwargs):
        # Auto-generates SKU if not provided, based on category and a sequence
        if not self.sku:
            prefix = (self.category.name[:3].upper() if self.category and self.category.name else 'PRD')
            # Find the highest existing SKU for this category prefix
            existing_skus = Product.objects.filter(sku__startswith=prefix).values_list('sku', flat=True)
            max_num = 0
            for sku in existing_skus:
                match = re.match(rf"{prefix}[-]?(\d+)", sku)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
            next_num = max_num + 1
            self.sku = f"{prefix}-{next_num:04d}"
        super().save(*args, **kwargs)


class ProductUnitPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="unit_prices")
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE)
    conversion_factor = models.FloatField(default=1.0) 
    price = models.DecimalField(max_digits=10, decimal_places=0)

    class Meta:
        unique_together = ('product', 'unit')

    def __str__(self):
        return f"{self.product.name} - {self.unit.name} ({self.price}/-)"


class StoreLocation(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='store_locations', null=True, blank=True)
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.branch.name if self.branch else 'No Branch'})"
    
    @property
    def total_products(self): # Count of products with stock at the store
        return self.inventory_set.count()

    @property
    def total_stock_items(self): # Sum of stock levels for all products
        return sum(inv.quantity_in_stock for inv in self.inventory_set.all())


class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventories')
    store = models.ForeignKey(StoreLocation, on_delete=models.CASCADE)
    quantity_in_stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=10)

    class Meta:
        unique_together = ('product', 'store')

    def __str__(self):
        return f"{self.product.name} @ {self.store.name} ({self.store.branch.name if self.store.branch else 'No Branch'})"

    @property
    def is_below_reorder(self): 
        return self.quantity_in_stock <= self.reorder_level