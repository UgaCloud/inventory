from django.db import models
import uuid


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
    sku = models.CharField(max_length=100, unique=True)
    brand = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True)
    uuid_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def total_stock(self): # Total units across all stores
        return sum(item.quantity_in_stock for item in self.inventories.all())

    
    @property
    def default_price(self):
        unit = self.unit_prices.order_by('id').first()
        return unit.price if unit else None

    @property
    def total_sales_quantity(self): # All sales across orders
        return sum(item.quantity for item in self.salesorderitem_set.all())

    @property
    def total_purchase_quantity(self): # All purchases across orders
        return sum(item.quantity for item in self.purchaseorderitem_set.all())


class ProductUnitPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="unit_prices")
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE)
    conversion_factor = models.FloatField(default=1.0) 
    price = models.DecimalField(max_digits=10, decimal_places=0)

    class Meta:
        unique_together = ('product', 'unit')

    def __str__(self):
        return f"{self.product.name} - {self.unit.name} (${self.price})"


class StoreLocation(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    @property
    def total_products(self): # Count of products with stock at the store
        return self.inventory_set.count()

    @property
    def total_stock_items(self): # Sum of stock levels for all products
        return sum(inv.quantity_in_stock for inv in self.inventory_set.all())


class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventories')
    store = models.ForeignKey(StoreLocation, on_delete=models.CASCADE)
    quantity_in_stock = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)

    class Meta:
        unique_together = ('product', 'store')

    def __str__(self):
        return f"{self.product.name} @ {self.store.name}"

    @property
    def is_below_reorder(self): 
        return self.quantity_in_stock <= self.reorder_level