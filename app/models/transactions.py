from django.db import models
from django.db import transaction
from datetime import date, timedelta
import re
from django.db.models import F, Sum
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User


from app.constants import PURCHASE_ORDER_OPTIONS, SALE_ORDER_OPTIONS, STOCK_MOVEMENT_OPTIONS
from app.models.products import StoreLocation


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
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

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
    
    

    @property
    def total_inventory_value(self):
        return (
            InventoryBatch.objects.filter(store=self)
            .annotate(value=F('remaining_quantity') * F('unit_cost'))
            .aggregate(total=Sum('value'))['total']
            or 0
        )


class Sales(models.Model):
    receipt_no = models.CharField(max_length=50, unique=True, blank=True)
    customer = models.ForeignKey("app.Customer", on_delete=models.SET_NULL, null=True, blank=True)
    sale_date = models.DateField(auto_now_add=True)
    store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE)

    status = models.CharField(max_length=20, choices=SALE_ORDER_OPTIONS)

    recorded_by = models.ForeignKey("auth.User", on_delete=models.DO_NOTHING)

    amount_paid = models.PositiveBigIntegerField(default=0)
    balance = models.BigIntegerField(default=0)
    amount_received = models.PositiveBigIntegerField(default=0)
    change = models.PositiveBigIntegerField(default=0)

    note = models.TextField(blank=True, null=True)
    payment_method = models.ForeignKey("app.PaymentMethod", on_delete=models.RESTRICT, null=True, blank=True)
    total_amount = models.PositiveBigIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Cancellation fields
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        "auth.User", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='cancelled_sales'
    )
    cancellation_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-updated_at', 'created_at']
        indexes = [
            models.Index(fields=['is_cancelled', 'status']),
            models.Index(fields=['receipt_no']),
        ]

    def resolve_status(self):
        if self.is_cancelled:
            return 'CANCELLED'
        if self.balance == 0:
            return 'FULFILLED'
        if self.amount_paid > 0:
            return 'PARTIALLY_PAID'
        return 'PENDING'

    def save(self, *args, **kwargs):
        # Auto-generate receipt number if not provided
        if not self.receipt_no:
            current_year = date.today().year

            if hasattr(self.store, 'code') and self.store.code:
                store_prefix = self.store.code[:3].upper()
            else:
                store_prefix = self.store.name[:3].upper() if self.store.name else 'STR'

            prefix = f"{store_prefix}{current_year}"

            existing_receipts = Sales.objects.filter(
                receipt_no__startswith=prefix
            ).values_list('receipt_no', flat=True)

            max_num = 0
            for receipt in existing_receipts:
                match = re.match(rf"{prefix}[-]?(\d+)", receipt)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num

            self.receipt_no = f"{prefix}-{max_num + 1:04d}"

        # derive status from stored values
        self.status = self.resolve_status()

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
    
    def cancel_sale(self, user, reason=""):
        """Cancel the sale and return stock"""
        from django.db import transaction
        from django.utils import timezone
        from app.views.salehelp import return_stock_to_inventory
        
        if self.is_cancelled:
            return False, "Sale is already cancelled"
        
        try:
            with transaction.atomic():
                # Update sale fields
                self.is_cancelled = True
                self.cancelled_at = timezone.now()
                self.cancelled_by = user
                self.cancellation_reason = reason
                
                # Update status will happen in save()
                self.save()
                
                # Return stock to inventory
                return_stock_to_inventory(self)
                
                return True, "Sale cancelled successfully"
                
        except Exception as e:
            return False, f"Failed to cancel sale: {str(e)}"


class SalesItem(models.Model):
    order = models.ForeignKey("app.Sales", related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE)
    unit = models.ForeignKey("app.UnitOfMeasure", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    sale_price = models.DecimalField(max_digits=10, decimal_places=0)
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        unique_together = ("order", "product", "unit")
        indexes = [
            models.Index(fields=['order', 'is_cancelled']),
        ]

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
    requested_by = models.ForeignKey("auth.User", on_delete=models.DO_NOTHING)
    from_store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE, related_name="transfer_requests_out")
    to_store = models.ForeignKey("app.StoreLocation", on_delete=models.CASCADE, related_name="transfer_requests_in")
    department = models.ForeignKey("app.Department", null=True, blank=True, on_delete=models.CASCADE, related_name="transfer_requests")
    # Priority and required date were added later to support scheduling and urgency
    PRIORITY_CHOICES = [
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")
    required_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default="pending")
    request_date = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfer_requests')
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
    units = models.ForeignKey("app.UnitOfMeasure", on_delete=models.CASCADE)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("transfer_request", "product")

    def __str__(self):
        return f"{self.product.name} x {self.quantity} (Request {self.transfer_request.id})"


class StockTransfer(models.Model):
    TRANSFER_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_transit", "In Transit"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    transfer_request = models.ForeignKey(TransferRequest, on_delete=models.CASCADE, related_name="stock_transfers", null=True, blank=True)
    transfer_date = models.DateField(auto_now_add=True)
    from_store = models.ForeignKey(StoreLocation, on_delete=models.CASCADE, related_name="transfers_out")
    to_store = models.ForeignKey(StoreLocation, on_delete=models.CASCADE, related_name="transfers_in")
    completed_by = models.CharField(max_length=100, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=TRANSFER_STATUS_CHOICES, default="pending")
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        try:
            from_store = self.from_store.name if self.from_store else "N/A"
            to_store = self.to_store.name if self.to_store else "N/A"
            return f"Transfer ({self.id if self.id else 'unsaved'}) {from_store} → {to_store}"
        except Exception:
            return f"Transfer ({self.id if self.id else 'unsaved'})"

    class Meta:
        ordering = ['-transfer_date']
        
        indexes = [
            models.Index(fields=['from_store', 'status']),
            models.Index(fields=['status', 'from_store']),
        ]


    @property
    def total_items(self):
        return self.items.count()

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_value(self):
        total = 0
        for item in self.items.all():
            try:
                # Prefer batch cost if available
                batch = InventoryBatch.objects.filter(
                    product=item.product,
                    store=self.from_store
                ).order_by('-created_at').first()

                if batch:
                    total += batch.unit_cost * item.quantity
                else:
                    # fallback to product fallback price
                    total += (item.product.default_price or 0) * item.quantity

            except:
                total += 0

        return total


    def apply_inventory_changes(self):
        """
            Apply inventory changes when a transfer is completed using FIFO method.
            Deducts stock from source store's oldest batches first and creates new batches in destination store.
        """  
        if self.status != 'completed':
            raise ValidationError("Can only apply inventory changes for completed transfers")

        # Use a DB transaction to ensure atomicity across multiple model updates
        try:
            with transaction.atomic():
                # Lock the transfer row to avoid concurrent modifications
                StockTransfer.objects.select_for_update().get(pk=self.pk)

                for transfer_item in self.items.select_related('product').all():
                    quantity_needed = int(transfer_item.quantity)

                    # Select source batches excluding expired ones (expiry_date is null or >= today)
                    source_batches_qs = InventoryBatch.objects.select_for_update().filter(
                        product=transfer_item.product,
                        store=self.from_store,
                        remaining_quantity__gt=0
                    ).filter(models.Q(expiry_date__isnull=True) | models.Q(expiry_date__gte=timezone.now().date()))

                    source_batches = list(source_batches_qs.order_by('expiry_date', 'received_date'))

                    total_available = sum(batch.remaining_quantity for batch in source_batches)
                    if total_available < quantity_needed:
                        raise ValidationError(
                            f"Insufficient non-expired stock for {transfer_item.product.name} in {self.from_store.name}. "
                            f"Available: {total_available}, Required: {quantity_needed}"
                        )

                    transferred_batches = []

                    # Consume batches FIFO
                    remaining = quantity_needed
                    for source_batch in source_batches:
                        if remaining <= 0:
                            break
                        take = min(source_batch.remaining_quantity, remaining)

                        # Reduce source batch
                        source_batch.remaining_quantity = models.F('remaining_quantity') - take
                        source_batch.save(update_fields=['remaining_quantity'])
                        # Refresh value
                        source_batch.refresh_from_db()

                        # Create destination batch preserving expiry and unit_cost
                        dest_batch = InventoryBatch.objects.create(
                            product=transfer_item.product,
                            store=self.to_store,
                            quantity=take,
                            remaining_quantity=take,
                            unit_cost=source_batch.unit_cost,
                            expiry_date=source_batch.expiry_date,
                            created_at=timezone.now()
                        )

                        transferred_batches.append({
                            'source_batch': source_batch,
                            'dest_batch': dest_batch,
                            'quantity': take
                        })

                        remaining -= take

                    # Update Inventory rows (lock them)
                    from app.models.products import Inventory as InventoryModel

                    # Get inventory records
                    source_inventory, _ = InventoryModel.objects.select_for_update().get_or_create(
                        store=self.from_store,
                        product=transfer_item.product,
                        defaults={'quantity_in_stock': 0}
                    )
                    dest_inventory, _ = InventoryModel.objects.select_for_update().get_or_create(
                        store=self.to_store,
                        product=transfer_item.product,
                        defaults={'quantity_in_stock': 0}
                    )

                    # Note: Source stock was already deducted when transfer was created (via signals)
                    # We only need to add to destination here
                    # Refresh to get current values for audit log
                    source_inventory.refresh_from_db()
                    
                    # Add to destination inventory
                    dest_inventory.quantity_in_stock = models.F('quantity_in_stock') + quantity_needed
                    dest_inventory.save(update_fields=['quantity_in_stock'])
                    
                    # Refresh to get actual integer value for audit log
                    dest_inventory.refresh_from_db()

                    # Create StockMovement entries for audit
                    for bt in transferred_batches:
                        username = str(self.created_by) if self.created_by else 'system'
                        StockMovement.objects.create(
                            store=self.from_store,
                            product=transfer_item.product,
                            transaction_type='stock_transfer_out',
                            quantity=-bt['quantity'],
                            transaction_id=self.id,
                            units_in_stock=source_inventory.quantity_in_stock,
                            note=(f"Transfer #{self.id} to {self.to_store.name} (Batch #{bt['source_batch'].id})"),
                            user=username
                        )

                        StockMovement.objects.create(
                            store=self.to_store,
                            product=transfer_item.product,
                            transaction_type='stock_transfer_in',
                            quantity=bt['quantity'],
                            units_in_stock=dest_inventory.quantity_in_stock,
                            transaction_id=self.id,
                            note=(f"Transfer #{self.id} from {self.from_store.name} (New Batch #{bt['dest_batch'].id})"),
                            user=username
                        )

                # Mark completed_by and save transfer
                self.completed_by = str(self.created_by) if self.created_by else None
                self.save(update_fields=['completed_by'])

        except ValidationError:
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ValidationError(f"Error applying inventory changes: {str(e)}")


class StockTransferItem(models.Model):
    stock_transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    units = models.ForeignKey("app.UnitOfMeasure", on_delete=models.SET_NULL, null=True, blank=True)
    transfer_request_item = models.ForeignKey(
        "app.TransferRequestItem", on_delete=models.SET_NULL, null=True, blank=True, related_name="fulfilled_transfer_items"
    )

    class Meta:
        unique_together = ("stock_transfer", "product")
        
        indexes = [
            models.Index(fields=['product', 'stock_transfer']),
            models.Index(fields=['stock_transfer', 'product']),
        ]

    @property
    def total_quantity(self):
        return self.quantity
    
    @property
    def total_value(self):
        """
        Value of this single transfer item based on FIFO batch cost or product default price.
        """
        try:
            batch = InventoryBatch.objects.filter(
                product=self.product,
                store=self.stock_transfer.from_store
            ).order_by('-created_at').first()

            if batch:
                return batch.unit_cost * self.quantity

            # fallback to product default price
            return (self.product.default_price or 0) * self.quantity

        except:
            return 0

    @property
    def unit_cost(self):
        """
        The cost per unit used to compute total value (FIFO batch cost or default price).
        """

        # Try FIFO batch cost first
        batch = InventoryBatch.objects.filter(
            product=self.product,
            store=self.stock_transfer.from_store
        ).order_by('-created_at').first()

        if batch:
            return batch.unit_cost

        # fallback to product default price
        return self.product.default_price or 0

    @property
    def available_stock(self):
        """
        Returns available quantity of this product in the FROM store before/after transfer.
        Uses Inventory table.
        """
        try:
            from app.models.products import Inventory

            inventory = Inventory.objects.filter(
                store=self.stock_transfer.from_store,
                product=self.product
            ).first()

            return inventory.quantity_in_stock if inventory else 0
        except:
            return 0

    
    def apply_fifo_transfer(self):
        pass
        # Deduct from source store using FIFO and expiry
        # batches = InventoryBatch.objects.filter(
        #     product=self.product,
        #     store=self.stock_transfer.from_store,
        #     remaining_quantity__gt=0,
        #     expiry_date__gte=date.today()
        # ).order_by('expiry_date', 'received_date')
        # to_deduct = self.quantity
        # for batch in batches:
        #     if batch.remaining_quantity >= to_deduct:
        #         batch.remaining_quantity -= to_deduct
        #         batch.save()
        #         break
        #     else:
        #         to_deduct -= batch.remaining_quantity
        #         batch.remaining_quantity = 0
        #         batch.save()
        #     # Add to destination store as new batch (preserve expiry)
        #     InventoryBatch.objects.create(
        #         product=self.product,
        #         store=self.stock_transfer.to_store,
        #         quantity=self.quantity,
        #         remaining_quantity=self.quantity,
        #         expiry_date=batch.expiry_date if batch else None,
        #         purchase_order_item=None
        #     )


class StockAdjustment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('applied', 'Applied'),
        ('cancelled', 'Cancelled'),
    ]
    store = models.ForeignKey('app.StoreLocation', on_delete=models.CASCADE, related_name='stock_adjustments')
    reference = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    created_by = models.ForeignKey(User, verbose_name=("Created By"), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True, null=True)
    product = models.ForeignKey('app.Product', on_delete=models.CASCADE)
    unit = models.ForeignKey('app.UnitOfMeasure', on_delete=models.SET_NULL, null=True, blank=True)
    quantity_change = models.IntegerField()
    reason = models.TextField(blank=True, null=True)
    unit_cost = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Adjustment'
        verbose_name_plural = 'Stock Adjustments'
        unique_together = ('reference', 'product', 'unit')

    def __str__(self):
        ref = self.reference or f"ADJ-{self.id}"
        return f"Adjustment {ref}: {self.product.name} {self.quantity_change} ({self.unit}) @ {self.store.name}"

    @property
    def is_batch(self):
        return bool(self.reference)

    @property
    def total_items_for_reference(self):
        """If this row is part of a batch (reference), return count of rows in the same batch."""
        if not self.reference:
            return 1
        return StockAdjustment.objects.filter(reference=self.reference, store=self.store).count()

    @property
    def total_quantity_changed_for_reference(self):
        if not self.reference:
            return self.quantity_change
        return StockAdjustment.objects.filter(reference=self.reference, store=self.store).aggregate(
            total=models.Sum('quantity_change')
        )['total'] or 0

    def apply_to_inventory(self):
        """
        Apply this single adjustment row to inventory and create a StockMovement record.
        Locks inventory row to avoid race conditions.
        """
        from django.db import transaction
        from django.utils import timezone
        from app.models.products import Inventory
        # import StockMovement here to avoid circular import at module load
        from app.models.transactions import StockMovement

        store = self.store

        with transaction.atomic():
            inv, created = Inventory.objects.select_for_update().get_or_create(
                product=self.product,
                store=store,
                defaults={'quantity_in_stock': 0}
            )

            inv.quantity_in_stock = inv.quantity_in_stock + int(self.quantity_change)
            if inv.quantity_in_stock < 0:
                # Business decision: prevent negative stock; clamp to zero
                inv.quantity_in_stock = 0
            inv.save(update_fields=['quantity_in_stock'])

            # Record movement for audit
            StockMovement.objects.create(
                product=self.product,
                store=store,
                transaction_type='ADJUSTMENT',
                quantity=self.quantity_change,
                transaction_id=self.id,
                note=self.reason or f'Adjustment {self.reference or self.id}',
                units_in_stock=inv.quantity_in_stock,
                user=self.created_by
            )

            # If positive change and unit_cost provided, create a batch for traceability
            if self.quantity_change > 0 and self.unit_cost:
                InventoryBatch.objects.create(
                    product=self.product,
                    store=store,
                    quantity=self.quantity_change,
                    unit_cost=self.unit_cost,
                    remaining_quantity=self.quantity_change,
                    expiry_date=None,
                    purchase_order_item=None
                )

    def apply(self, applied_by=None):
        """
        Apply this adjustment. If this row has a `reference`, apply all pending rows with the same reference.
        Otherwise apply only this row.
        Marks affected rows as 'applied' and sets approved_by/approved_at.
        """
        from django.db import transaction
        from django.utils import timezone

        # Gather target rows to apply
        if self.reference:
            qs = StockAdjustment.objects.select_for_update().filter(
                reference=self.reference, store=self.store, status='pending'
            )
        else:
            qs = StockAdjustment.objects.select_for_update().filter(pk=self.pk, status='pending')

        if not qs.exists():
            return False

        with transaction.atomic():
            for adj in qs:
                adj.apply_to_inventory()
                adj.status = 'applied'
                adj.save(update_fields=['status'])
        return True


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


class StockAdjustmentItem(models.Model):
    stock_adjustment = models.ForeignKey('StockAdjustment', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('app.Product', on_delete=models.CASCADE)
    unit = models.ForeignKey('app.UnitOfMeasure', on_delete=models.SET_NULL, null=True, blank=True)
    quantity_change = models.IntegerField()
    unit_cost = models.PositiveIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('stock_adjustment', 'product', 'unit')
        verbose_name = 'Stock Adjustment Item'
        verbose_name_plural = 'Stock Adjustment Items'

    def __str__(self):
        return f"{self.product.name} {self.quantity_change} ({self.unit}) for Adjustment {self.stock_adjustment.reference or self.stock_adjustment.id}"
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    