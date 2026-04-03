from django.db import models
import uuid
from app.models.organization import Branch
from django.core.exceptions import ValidationError
import re
from django.db.models import Sum

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

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


class Automotive(models.Model):
    brand = models.CharField(max_length=100)  # E.g., "Toyota"
    model = models.CharField(max_length=100)  # E.g., "Corolla"
    year_from = models.IntegerField()
    year_to = models.IntegerField(blank=True, null=True)
    engine_type = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.brand} {self.model} ({self.year_from}-{self.year_to or 'Present'})"

    def clean(self):
        if self.year_to and self.year_from > self.year_to:
            raise ValidationError("Year from cannot be greater than year to.")


class Product(models.Model):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True, blank=True)  
    brand = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    compatible_vehicles = models.ManyToManyField(Automotive, blank=True, related_name='products', verbose_name='Compatibility')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.brand})"

    @property
    def total_stock(self):
        """Total units across all stores IN BASE UNITS"""
        return sum(item.quantity_in_stock for item in self.inventories.all())


    @property
    def available_stock(self):
        from app.models.transactions import StockTransferItem
        total_physical_stock = self.total_stock
        committed_stock = StockTransferItem.objects.filter(
            product=self,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('base_quantity'))['committed'] or 0
        return max(0, total_physical_stock - committed_stock)



    # @property
    # def available_stock(self):
    #     from app.models.transactions import StockTransferItem
        
    #     """Real-time available stock across all stores (minus committed stock) IN BASE UNITS"""
    #     total_physical_stock = self.total_stock
        
    #     # Calculate committed stock from pending/in-transit transfers IN BASE UNITS
    #     committed_stock = StockTransferItem.objects.filter(
    #         product=self,
    #         stock_transfer__status__in=['pending', 'in_transit']
    #     ).aggregate(committed=Sum('base_quantity'))['committed'] or 0  # FIXED: base_quantity
        
    #     return total_physical_stock
    #     # return max(0, total_physical_stock - committed_stock)

    @property
    def committed_stock(self):
        from app.models.transactions import StockTransferItem
        """Stock reserved for pending/in-transit transfers IN BASE UNITS"""
        return StockTransferItem.objects.filter(
            product=self,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('base_quantity'))['committed'] or 0  # FIXED: base_quantity

    @property
    def stock_by_store(self):
        from app.models.transactions import StockTransferItem
        """Detailed stock breakdown by store with real-time availability IN BASE UNITS"""
        stores_data = []
        for inventory in self.inventories.select_related('store').all():
            # Calculate committed stock for this specific store IN BASE UNITS
            committed_stock = StockTransferItem.objects.filter(
                product=self,
                stock_transfer__from_store=inventory.store,
                stock_transfer__status__in=['pending', 'in_transit']
            ).aggregate(committed=Sum('base_quantity'))['committed'] or 0  # FIXED: base_quantity
            
            stores_data.append({
                'store': inventory.store.name,
                'physical_stock': inventory.quantity_in_stock,  # Already base units
                'committed_stock': committed_stock,
                'available_stock': max(0, inventory.quantity_in_stock - committed_stock),
                'reorder_level': inventory.reorder_level,
                'last_updated': inventory.last_updated
            })
        return stores_data

    @property
    def low_stock_stores(self):
        """Stores where this product is below reorder level (BASE UNITS)"""
        low_stock = []
        for store_data in self.stock_by_store:
            if store_data['available_stock'] <= store_data['reorder_level']:
                low_stock.append(store_data)
        return low_stock

    @property
    def out_of_stock_stores(self):
        """Stores where this product is out of stock (BASE UNITS)"""
        return [store for store in self.stock_by_store if store['available_stock'] == 0]

    def get_stock_for_store(self, store):
        """Get real-time stock for a specific store IN BASE UNITS"""
        from app.models.transactions import StockTransferItem
        try:
            inventory = self.inventories.get(store=store)
            committed_stock = StockTransferItem.objects.filter(
                product=self,
                stock_transfer__from_store=store,
                stock_transfer__status__in=['pending', 'in_transit']
            ).aggregate(committed=Sum('base_quantity'))['committed'] or 0  # FIXED: base_quantity
            
            return {
                'physical_stock': inventory.quantity_in_stock,
                'committed_stock': committed_stock,
                'available_stock': max(0, inventory.quantity_in_stock - committed_stock),
                'reorder_level': inventory.reorder_level
            }
        except Inventory.DoesNotExist:
            return {
                'physical_stock': 0,
                'committed_stock': 0,
                'available_stock': 0,
                'reorder_level': 0
            }

    def default_unit(self):
        unit = self.unit_prices.order_by('id').first()
        return unit.unit if unit else "Piece"
    
    @property
    def default_price(self):
        unit = self.unit_prices.order_by('id').first()
        return unit.price if unit else 0

    @property
    def total_sales_quantity(self):
        """Total sales quantity IN BASE UNITS"""
        return sum(item.base_quantity for item in self.salesorderitem_set.all())  # FIXED: base_quantity

    @property
    def total_purchase_quantity(self):
        """Total purchase quantity IN BASE UNITS"""
        return sum(item.base_quantity for item in self.purchaseorderitem_set.all())  # FIXED: base_quantity
    
    def get_conversion_factors(self):
        """Get all conversion factors for this product"""
        factors = {}
        for unit_price in self.unit_prices.all():
            factors[unit_price.unit.name] = {
                'conversion_factor': unit_price.conversion_factor,
                'price': unit_price.price,
                'is_base': unit_price.conversion_factor == 1
            }
        return factors
    
    def get_base_unit(self):
        """Get the base unit for this product"""
        base_unit_price = self.unit_prices.filter(conversion_factor=1).first()
        return base_unit_price.unit if base_unit_price else None

    def save(self, *args, **kwargs):
        if not self.sku:
            prefix = (self.category.name[:3].upper() if self.category and self.category.name else 'PRD')
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

        if not self.barcode:
            self.barcode = self._generate_unique_barcode()
        super().save(*args, **kwargs)

    def _generate_unique_barcode(self):
        # Generate a numeric POS-friendly barcode-like value (13 digits).
        # It is not EAN validated, but works for scanner/lookup operations.
        while True:
            candidate = str(uuid.uuid4().int)[:13]
            if not Product.objects.filter(barcode=candidate).exclude(pk=self.pk).exists():
                return candidate


class ProductUnitPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="unit_prices")
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE)
    conversion_factor = models.DecimalField(max_digits=10, decimal_places=0, default=1)
    price = models.DecimalField(max_digits=10, decimal_places=0)
    
    class Meta:
        unique_together = ('product', 'unit')
        ordering = ['conversion_factor']  # Base unit should be first (CF=1)

    def __str__(self):
        return f"{self.product.name} - {self.unit.name} ({self.price}/-)"
    
    # def clean(self):
    #     if self.conversion_factor <= 0:
    #         raise ValidationError("Conversion factor must be positive")

    #     if self.conversion_factor % 1 != 0:
    #         raise ValidationError(
    #             "Conversion factor must produce whole base units"
    #         )
            
    #     if self.conversion_factor != 1 and self.price is not None:
    #         raise ValidationError(
    #             "Only the base unit (conversion_factor = 1) may have a stored price. "
    #             "All other unit prices are derived."
    #         )
    
    def save(self, *args, **kwargs):
        if self.conversion_factor <= 0:
            raise ValidationError("Conversion factor must be greater than 0")
        
        # REMOVED: single base unit enforcement
        # if self.conversion_factor == 1:
        #     exists = ProductUnitPrice.objects.filter(
        #         product=self.product,
        #         conversion_factor=1
        #     ).exclude(pk=self.pk).exists()

        #     if exists:
        #         raise ValidationError(
        #             "A product can only have one base unit (conversion factor = 1)"
        #         )

        super().save(*args, **kwargs)



class StoreLocation(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='store_locations', null=True, blank=True)
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.branch.name if self.branch else 'No Branch'})"
    
    @property
    def total_products(self):
        return self.inventory_set.values('product').distinct().count()

    @property
    def total_stock_items(self):
        """Total stock items IN BASE UNITS"""
        return sum(inv.quantity_in_stock for inv in self.inventory_set.all())


class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventories')
    store = models.ForeignKey(StoreLocation, on_delete=models.CASCADE)
    quantity_in_stock = models.PositiveIntegerField(default=0)  # ALWAYS BASE UNITS
    reorder_level = models.PositiveIntegerField(default=10)     # IN BASE UNITS
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'store')
        indexes = [
            models.Index(fields=['product', 'store']),
            models.Index(fields=['store', 'product']),
            models.Index(fields=['last_updated']),
        ]
        
    def save(self, *args, **kwargs):
        if self.quantity_in_stock < 0:
            raise ValidationError("Inventory cannot be negative")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} @ {self.store.name} ({self.store.branch.name if self.store.branch else 'No Branch'})"

    @property
    def is_below_reorder(self): 
        return self.quantity_in_stock <= self.reorder_level