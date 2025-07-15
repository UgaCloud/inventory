from django.db import models

from app.constants import PURCHASE_ORDER_OPTIONS, SALE_ORDER_OPTIONS, STOCK_MOVEMENT_OPTIONS


class PurchaseOrder(models.Model):
    supplier = models.ForeignKey("app.Supplier", on_delete=models.CASCADE)
    store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE)
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

    class Meta:
        unique_together = ("order", "product", "unit")

    @property
    def total_cost(self):
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

    class Meta:
        unique_together = ("order", "product", "unit")

    def get_total_price(self):
        return self.quantity * self.sale_price


class TransferRequest(models.Model):
    REQUEST_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("fulfilled", "Fulfilled"),
    ]
    requested_by = models.CharField(max_length=100)
    from_store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE, related_name="transfer_requests_out")
    to_store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE, related_name="transfer_requests_in")
    status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default="pending")
    request_date = models.DateTimeField(auto_now_add=True)
    approved_by = models.CharField(max_length=100, blank=True, null=True)
    approved_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Request {self.id}: {self.from_store.name} → {self.to_store.name}"

    @property
    def total_requested_items(self):
        return self.stock_transfers.aggregate(total=models.Sum('items__quantity'))['total'] or 0


class TransferRequestItem(models.Model):
    transfer_request = models.ForeignKey('TransferRequest', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('app.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    units = models.ForeignKey("app.ProductUnitPrice", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("transfer_request", "product")

    def __str__(self):
        return f"{self.product.name} x {self.quantity} (Request {self.transfer_request.id})"


class StockTransfer(models.Model):
    transfer_request = models.ForeignKey(TransferRequest, on_delete=models.CASCADE, related_name="stock_transfers")
    transfer_date = models.DateField(auto_now_add=True)
    completed_by = models.CharField(max_length=100, blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Transfer {self.id} for Request {self.transfer_request.id}"

    @property
    def total_items(self):
        return self.items.count()

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())


class StockTransferItem(models.Model):
    stock_transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    transfer_request_item = models.ForeignKey(
        "app.TransferRequestItem", on_delete=models.SET_NULL, null=True, blank=True, related_name="fulfilled_transfer_items"
    )

    class Meta:
        unique_together = ("stock_transfer", "product")

    def __str__(self):
        return f"{self.product.name} x {self.quantity} (Transfer {self.stock_transfer.id})"

    @property
    def total_quantity(self):
        return self.quantity


class StockMovement(models.Model):
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE, related_name="stock_movements")
    store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=50, choices=STOCK_MOVEMENT_OPTIONS)
    quantity = models.IntegerField()
    transaction_id = models.IntegerField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    units_in_stock = models.IntegerField()
    user = models.CharField(max_length=50)


