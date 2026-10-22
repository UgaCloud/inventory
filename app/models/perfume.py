from django.db import models
from app.managers import TenantManager


class PerfumeSaleLine(models.Model):

    """
    A perfume sale recorded in millilitres: either a single perfume or a
    mixture of two or more existing perfumes.

    This is metadata on the parent Sales record. It never holds stock of its
    own -- quantities are consumed from each component product's existing
    Inventory / InventoryBatch records, so a mixture never duplicates the
    stock of its component perfumes.
    """
    objects = TenantManager()
    sale = models.ForeignKey('app.Sales', related_name='perfume_lines', on_delete=models.CASCADE)
    total_quantity_ml = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=14, decimal_places=2)
    # FIFO cost snapshot taken when the stock was consumed (historical).
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # True once the component stock has been restored (e.g. on cancellation).
    # Guards against duplicate stock restoration if reprocessed.
    is_cancelled = models.BooleanField(default=False)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Perfume {self.total_quantity_ml}ml ({self.sale.receipt_no})"

    @property
    def component_count(self):
        return self.components.count()

    @property
    def is_mixture(self):
        return self.component_count > 1

    @property
    def gross_profit(self):
        """Gross profit = selling price - recorded FIFO cost."""
        return (self.selling_price or 0) - (self.total_cost or 0)


class PerfumeSaleComponent(models.Model):

    """
    One component perfume consumed by a PerfumeSaleLine.

    Stores the exact quantity consumed plus cost snapshots taken at sale time,
    so historical cost/profit reporting survives later cost changes and stock
    restoration returns the correct value.
    """
    objects = TenantManager()
    line = models.ForeignKey('app.PerfumeSaleLine', related_name='components', on_delete=models.CASCADE)
    product = models.ForeignKey(
        'app.Product', on_delete=models.CASCADE, related_name='perfume_sale_components'
    )
    quantity_ml = models.DecimalField(max_digits=12, decimal_places=2)  # ml as entered
    base_quantity = models.PositiveIntegerField(default=0)  # consumed qty in BASE UNITS (integer)
    # Snapshot of the FIFO unit cost per base unit at the time of sale.
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    # Snapshot of the total cost of this component's consumed quantity.
    component_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.product.name} {self.quantity_ml}ml"
