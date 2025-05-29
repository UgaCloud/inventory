from django.db import models

from app.constants import PURCHASE_ORDER_OPTIONS, SALE_ORDER_OPTIONS, STOCK_MOVEMENT_OPTIONS


class PurchaseOrder(models.Model):
    supplier = models.ForeignKey("app.Supplier", on_delete=models.CASCADE)
    purchase_date = models.DateField(auto_now_add=True)
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=PURCHASE_ORDER_OPTIONS)
    recorded_by = models.CharField(max_length=50)

    def __str__(self):
        return f"PO-{self.id} ({self.supplier.name})"
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_cost(self):
        return sum(item.cost() for item in self.items.all())



class PurchaseOrderItem(models.Model):
    order = models.ForeignKey("app.PurchaseOrder", related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE)
    unit = models.ForeignKey("app.UnitOfMeasure", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=0)

    @property
    def cost(self):
        return self.quantity * self.unit_cost


class Sales(models.Model):
    customer = models.ForeignKey("app.Customer", on_delete=models.SET_NULL, null=True, blank=True)
    sale_date = models.DateField(auto_now_add=True)
    store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=SALE_ORDER_OPTIONS)
    recorded_by = models.CharField(max_length=50)

    def __str__(self):
        return f"SO-{self.id} ({self.customer.name if self.customer else 'Walk-in'})"
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_price(self):
        return sum(item.get_total_price() for item in self.items.all())



class SalesItem(models.Model):
    order = models.ForeignKey("app.Sales", related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE)
    unit = models.ForeignKey("app.UnitOfMeasure", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    sale_price = models.DecimalField(max_digits=10, decimal_places=0)

    def get_total_price(self):
        return self.quantity * self.sale_price


class StockTransfer(models.Model):
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE)
    from_store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE, related_name='outgoing_transfers')
    to_store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE, related_name='incoming_transfers')
    quantity = models.PositiveIntegerField()
    transfer_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name}: {self.from_store.name} → {self.to_store.name}"

class StockMovement(models.Model):
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE)
    store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=10, choices=STOCK_MOVEMENT_OPTIONS)
    quantity = models.IntegerField()
    related_order_id = models.IntegerField(null=True, blank=True)
    note = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
