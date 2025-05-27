from django.db import models
import uuid

# -----------------------------
# Core Product Models
# -----------------------------

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class UnitOfMeasure(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g., "Box"
    abbreviation = models.CharField(max_length=10)        # e.g., "bx"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True)
    uuid_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def total_stock(self):
        return sum(i.quantity_in_stock for i in self.inventory_set.all())

    @property
    def default_price(self):
        unit = self.unit_prices.order_by('id').first()
        return unit.price if unit else None


class ProductUnitPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="unit_prices")
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE)
    conversion_factor = models.FloatField(default=1.0)  # base unit = 1.0
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('product', 'unit')

    def __str__(self):
        return f"{self.product.name} - {self.unit.name} (${self.price})"


# -----------------------------
# Inventory and Store Models
# -----------------------------

class StoreLocation(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
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


# -----------------------------
# Order Models
# -----------------------------

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact_info = models.TextField(blank=True)

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    order_date = models.DateField(auto_now_add=True)
    expected_date = models.DateField(null=True, blank=True)
    is_fulfilled = models.BooleanField(default=False)

    def __str__(self):
        return f"PO-{self.id} ({self.supplier.name})"


class PurchaseOrderItem(models.Model):
    order = models.ForeignKey(PurchaseOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)

    def get_total_cost(self):
        return self.quantity * self.cost_price


class Customer(models.Model):
    name = models.CharField(max_length=255)
    contact_info = models.TextField(blank=True)

    def __str__(self):
        return self.name


class SalesOrder(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    order_date = models.DateField(auto_now_add=True)
    store = models.ForeignKey(StoreLocation, on_delete=models.CASCADE)

    def __str__(self):
        return f"SO-{self.id} ({self.customer.name if self.customer else 'Walk-in'})"


class SalesOrderItem(models.Model):
    order = models.ForeignKey(SalesOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)

    def get_total_price(self):
        return self.quantity * self.sale_price


# -----------------------------
# Stock Transfer (Optional)
# -----------------------------

class StockTransfer(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    from_store = models.ForeignKey(StoreLocation, on_delete=models.CASCADE, related_name='outgoing_transfers')
    to_store = models.ForeignKey(StoreLocation, on_delete=models.CASCADE, related_name='incoming_transfers')
    quantity = models.PositiveIntegerField()
    transfer_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name}: {self.from_store.name} → {self.to_store.name}"
