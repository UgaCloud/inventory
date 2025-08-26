from django.db import models
from datetime import date, timedelta
import re

from app.constants import PURCHASE_ORDER_OPTIONS, SALE_ORDER_OPTIONS, STOCK_MOVEMENT_OPTIONS


class PurchaseOrder(models.Model):
    supplier = models.ForeignKey("app.Supplier", on_delete=models.CASCADE)
    store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE)
    purchase_date = models.DateField(auto_now_add=True)
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=PURCHASE_ORDER_OPTIONS)
    recorded_by = models.CharField(max_length=50)
    note = models.TextField(blank=True, null=True)  
    total_cost = models.DecimalField(max_digits=16, decimal_places=2, default=0)  

    def __str__(self):
        return f"PO-{self.id} ({self.supplier.name})"
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    def update_total_cost(self):
        self.total_cost = sum(item.cost for item in self.items.all())
        self.save(update_fields=["total_cost"])



class PurchaseOrderItem(models.Model):
    order = models.ForeignKey("app.PurchaseOrder", related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE)
    unit = models.ForeignKey("app.UnitOfMeasure", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=0)
    expiry_date = models.DateField(null=True, blank=True) 

    class Meta:
        unique_together = ("order", "product", "unit")

    @property
    def cost(self):
        return self.quantity * self.unit_cost

    def __str__(self):
        return f"POI-{self.id}: {self.product.name} x {self.quantity} @ {self.unit} (Order {self.order.id})"


class InventoryBatch(models.Model):
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE, related_name="batches")
    store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=0)
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
    receipt_no = models.CharField(max_length=50, unique=True, blank=True)  # Allow blank for auto-generation
    customer = models.ForeignKey("app.Customer", on_delete=models.SET_NULL, null=True, blank=True)
    sale_date = models.DateField(auto_now_add=True)
    store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=SALE_ORDER_OPTIONS)
    recorded_by = models.CharField(max_length=50)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    amount_received = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    change = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    note = models.TextField(blank=True, null=True)  
    payment_method = models.ForeignKey("app.PaymentMethod", on_delete=models.RESTRICT, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=16, decimal_places=0, default=0)

    def save(self, *args, **kwargs):
        # Auto-generate receipt number if not provided
        if not self.receipt_no:
            # Create prefix based on store and current year
            current_year = date.today().year
            if hasattr(self.store, 'code') and self.store.code:
                store_prefix = self.store.code[:3].upper()
            else:
                store_prefix = self.store.name[:3].upper() if self.store.name else 'STR'
            
            prefix = f"{store_prefix}{current_year}"
            
            # Find the highest existing receipt number for this prefix
            existing_receipts = Sales.objects.filter(receipt_no__startswith=prefix).values_list('receipt_no', flat=True)
            max_num = 0
            for receipt in existing_receipts:
                # Extract number from receipt format: STR2024-0001
                match = re.match(rf"{prefix}[-]?(\d+)", receipt)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
            
            next_num = max_num + 1
            self.receipt_no = f"{prefix}-{next_num:04d}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"SO-{self.receipt_no} ({self.customer.name if self.customer else 'Walk-in'})"
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    def update_total_amount(self):
        self.total_amount = sum(item.amount() for item in self.items.all())
        self.save(update_fields=["total_amount"])

    @property
    def number_of_items(self):
        return self.items.count()


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

    def __str__(self):
        return f"{self.product.name} x {self.quantity} @ {self.sale_price} (Order {self.order.receipt_no})"


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
    units = models.ForeignKey("app.ProductUnitPrice", on_delete=models.SET_NULL, null=True, blank=True)
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


class StockAdjustment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('applied', 'Applied'),
        ('cancelled', 'Cancelled'),
    ]
    store = models.ForeignKey('app.StoreLocation', on_delete=models.CASCADE, related_name='stock_adjustments')
    reference = models.CharField(max_length=100, blank=True, null=True)
    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.CharField(max_length=100, blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Adjustment'
        verbose_name_plural = 'Stock Adjustments'

    def __str__(self):
        return f"Adjustment {self.id} @ {self.store.name} ({self.status})"

    @property
    def total_items(self):
        return self.items.count()

    @property
    def total_quantity_changed(self):
        return sum(item.quantity_change for item in self.items.all())

    def apply(self, applied_by=None):
        """
        Apply the stock adjustment: update Inventory.quantity_in_stock and create StockMovement records.
        Marks adjustment as 'applied' when complete. Uses a database transaction and locks inventory rows.
        """
        from django.db import transaction
        from app.models.products import Inventory
        from app.models.products import Product, UnitOfMeasure
        # import StockMovement here to avoid circular import at module load
        from app.models.transactions import StockMovement

        if self.status == 'applied':
            return False

        with transaction.atomic():
            for item in self.items.select_for_update():
                item.apply_to_inventory()

            self.status = 'applied'
            if applied_by:
                self.approved_by = applied_by
            from django.utils import timezone
            self.approved_at = timezone.now()
            self.save(update_fields=['status', 'approved_by', 'approved_at'])
        return True


class StockAdjustmentItem(models.Model):
    adjustment = models.ForeignKey(StockAdjustment, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('app.Product', on_delete=models.CASCADE)
    unit = models.ForeignKey('app.UnitOfMeasure', on_delete=models.SET_NULL, null=True, blank=True)
    # positive -> add stock, negative -> reduce stock
    quantity_change = models.IntegerField()
    reason = models.CharField(max_length=255, blank=True, null=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Adjustment Item'
        verbose_name_plural = 'Stock Adjustment Items'
        unique_together = ('adjustment', 'product', 'unit')

    def __str__(self):
        return f"{self.product.name} {self.quantity_change} ({self.unit})"

    def apply_to_inventory(self):
        """
        Apply this item to the inventory for the adjustment's store.
        Creates a StockMovement record for auditing.
        """
        from django.db import transaction
        from app.models.products import Inventory
        from django.utils import timezone

        store = self.adjustment.store

        with transaction.atomic():
            # Get or create inventory row for product+store
            inv, created = Inventory.objects.select_for_update().get_or_create(
                product=self.product,
                store=store,
                defaults={'quantity_in_stock': 0}
            )

            # Apply change
            inv.quantity_in_stock = inv.quantity_in_stock + int(self.quantity_change)
            # Prevent negative stock unless business allows it
            if inv.quantity_in_stock < 0:
                inv.quantity_in_stock = 0
            inv.save(update_fields=['quantity_in_stock'])

            # Record stock movement for audit
            StockMovement.objects.create(
                product=self.product,
                store=store,
                transaction_type='ADJUSTMENT',
                quantity=self.quantity_change,
                transaction_id=self.adjustment.id,
                note=self.reason or f'Adjustment {self.adjustment.id}',
                units_in_stock=inv.quantity_in_stock,
                user=self.adjustment.created_by
            )
            # Optionally, if positive change and unit_cost provided, create a batch (preserve simple behaviour)
            if self.quantity_change > 0 and self.unit_cost:
                from app.models.transactions import InventoryBatch
                InventoryBatch.objects.create(
                    product=self.product,
                    store=store,
                    quantity=self.quantity_change,
                    unit_cost=self.unit_cost,
                    remaining_quantity=self.quantity_change,
                    expiry_date=None,
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

    def __str__(self):
        return f"{self.product.name} | {self.store.name} | {self.transaction_type} | {self.quantity} | {self.timestamp.strftime('%Y-%m-%d %H:%M')}"



