from django.db import models
import uuid
from app.models.organization import Branch
import re

from django.db.models import Sum



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
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.brand})"

    @property
    def total_stock(self):
        """Total units across all stores"""
        return sum(item.quantity_in_stock for item in self.inventories.all())

    @property
    def available_stock(self):
        from app.models.transactions import StockTransferItem
        
        """Real-time available stock across all stores (minus committed stock)"""
        total_physical_stock = self.total_stock
        
        # Calculate committed stock from pending/in-transit transfers
        committed_stock = StockTransferItem.objects.filter(
            product=self,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('quantity'))['committed'] or 0
        
        return max(0, total_physical_stock - committed_stock)

    @property
    def committed_stock(self):
        from app.models.transactions import StockTransferItem
        """Stock reserved for pending/in-transit transfers"""
        return StockTransferItem.objects.filter(
            product=self,
            stock_transfer__status__in=['pending', 'in_transit']
        ).aggregate(committed=Sum('quantity'))['committed'] or 0

    @property
    def stock_by_store(self):
        from app.models.transactions import StockTransferItem
        """Detailed stock breakdown by store with real-time availability"""
        stores_data = []
        for inventory in self.inventories.select_related('store').all():
            # Calculate committed stock for this specific store
            committed_stock = StockTransferItem.objects.filter(
                product=self,
                stock_transfer__from_store=inventory.store,
                stock_transfer__status__in=['pending', 'in_transit']
            ).aggregate(committed=Sum('quantity'))['committed'] or 0
            
            stores_data.append({
                'store': inventory.store.name,
                'physical_stock': inventory.quantity_in_stock,
                'committed_stock': committed_stock,
                'available_stock': max(0, inventory.quantity_in_stock - committed_stock),
                'reorder_level': inventory.reorder_level,
                'last_updated': inventory.last_updated
            })
        return stores_data

    @property
    def low_stock_stores(self):
        """Stores where this product is below reorder level"""
        low_stock = []
        for store_data in self.stock_by_store:
            if store_data['available_stock'] <= store_data['reorder_level']:
                low_stock.append(store_data)
        return low_stock

    @property
    def out_of_stock_stores(self):
        """Stores where this product is out of stock"""
        return [store for store in self.stock_by_store if store['available_stock'] == 0]

    def get_stock_for_store(self, store):
        """Get real-time stock for a specific store"""
        from app.models.transactions import StockTransferItem
        try:
            inventory = self.inventories.get(store=store)
            committed_stock = StockTransferItem.objects.filter(
                product=self,
                stock_transfer__from_store=store,
                stock_transfer__status__in=['pending', 'in_transit']
            ).aggregate(committed=Sum('quantity'))['committed'] or 0
            
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
        return sum(item.quantity for item in self.salesorderitem_set.all())

    @property
    def total_purchase_quantity(self):
        return sum(item.quantity for item in self.purchaseorderitem_set.all())

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
    def total_products(self):
        return self.inventory_set.values('product').distinct().count()


    @property
    def total_stock_items(self):
        return sum(inv.quantity_in_stock for inv in self.inventory_set.all())

    


class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventories')
    store = models.ForeignKey(StoreLocation, on_delete=models.CASCADE)
    quantity_in_stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=10)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'store')
      
        indexes = [
            models.Index(fields=['product', 'store']),
            models.Index(fields=['store', 'product']),
            models.Index(fields=['last_updated']),
        ]

    def __str__(self):
        return f"{self.product.name} @ {self.store.name} ({self.store.branch.name if self.store.branch else 'No Branch'})"

    @property
    def is_below_reorder(self): 
        return self.quantity_in_stock <= self.reorder_level