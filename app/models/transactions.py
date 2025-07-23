from django.db import models
from datetime import date, timedelta

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
    expiry_date = models.DateField(null=True, blank=True)  # <-- Added expiry date for purchase

    class Meta:
        unique_together = ("order", "product", "unit")

    @property
    def total_cost(self):
        return self.quantity * self.unit_cost

class InventoryBatch(models.Model):
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE, related_name="batches")
    store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    received_date = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateField(null=True, blank=True)
    remaining_quantity = models.PositiveIntegerField()
    purchase_order_item = models.ForeignKey("app.PurchaseOrderItem", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["expiry_date", "received_date"]  

    def __str__(self):
        return f"Batch {self.id}: {self.product.name} @ {self.store.name} ({self.remaining_quantity}/{self.quantity}) Expires: {self.expiry_date}"

    @property
    def is_expired(self):
        return self.expiry_date and self.expiry_date < date.today()

    @property
    def days_to_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - date.today()).days
        return None

    @classmethod
    def expiring_soon(cls, days=30):
        return cls.objects.filter(expiry_date__gte=date.today(), expiry_date__lte=date.today() + timedelta(days=days))

    @classmethod
    def expired(cls):
        return cls.objects.filter(expiry_date__lt=date.today())



class Sales(models.Model):
    receipt_no = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey("app.Customer", on_delete=models.SET_NULL, null=True, blank=True)
    sale_date = models.DateField(auto_now_add=True)
    store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=SALE_ORDER_OPTIONS)
    recorded_by = models.CharField(max_length=50)

    def __str__(self):
        return f"SO-{self.receipt_no} ({self.customer.name if self.customer else 'Walk-in'})"
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_amount(self):
        return sum(item.amount() for item in self.items.all())


class SalesItem(models.Model):
    order = models.ForeignKey("app.Sales", related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE)
    unit = models.ForeignKey("app.UnitOfMeasure", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    sale_price = models.DecimalField(max_digits=10, decimal_places=0)

    class Meta:
        unique_together = ("order", "product", "unit")

    def amount(self):
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

    def apply_fifo_transfer(self):
        # Deduct from source store using FIFO and expiry
        batches = InventoryBatch.objects.filter(
            product=self.product,
            store=self.stock_transfer.transfer_request.from_store,
            remaining_quantity__gt=0,
            expiry_date__gte=date.today()
        ).order_by('expiry_date', 'received_date')
        to_deduct = self.quantity
        for batch in batches:
            if batch.remaining_quantity >= to_deduct:
                batch.remaining_quantity -= to_deduct
                batch.save()
                break
            else:
                to_deduct -= batch.remaining_quantity
                batch.remaining_quantity = 0
                batch.save()
        # Add to destination store as new batch (preserve expiry)
        InventoryBatch.objects.create(
            product=self.product,
            store=self.stock_transfer.transfer_request.to_store,
            quantity=self.quantity,
            unit_cost=batch.unit_cost if batch else 0,
            remaining_quantity=self.quantity,
            expiry_date=batch.expiry_date if batch else None,
            purchase_order_item=None
        )


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


