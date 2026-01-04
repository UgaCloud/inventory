from django.db.models import Sum
from app.models.transactions import SalesItem

def get_top_categories_by_sales(limit=3):
    """
    Returns a queryset of top categories by total sales quantity, descending.
    Each result includes: category, total_sales (quantity).
    """
    from app.models.products import Category, Product
    return (
        Category.objects.annotate(
            total_sales=Sum('products__salesitem__quantity')
        )
        .order_by('-total_sales')[:limit]
    )
from app.models.products import Product, Category, UnitOfMeasure, ProductUnitPrice, Inventory, StoreLocation
from django.db import models
from app.models.transactions import InventoryBatch
from django.db.models import Sum, F

#product selectors
def get_all_products():
    return Product.objects.select_related('category').all()

def get_product_by_id(product_id):
    return Product.objects.select_related('category').get(id = product_id)

#category selectors
def get_category_by_id(category_id):
    return Category.objects.get(id = category_id)

def get_all_categories():
    return Category.objects.all()

#unit of measurement selectors
def get_all_units_of_measurement():
    return UnitOfMeasure.objects.all()

def get_unit_of_measurement_by_id(unit_id):
    return UnitOfMeasure.objects.get(id = unit_id)

def get_all_product_unit_prices():
    return ProductUnitPrice.objects.all()

def get_stores():
    return StoreLocation.objects.filter(is_active=True)


def get_low_stock_products(limit=10):
    """
    Get products with low stock (quantity <= reorder level).
    
    Args:
        limit (int): Maximum number of products to return. Default is 10.
                    Set to None for no limit.
    
    Returns:
        QuerySet: Inventory objects with low stock
    """
    queryset = Inventory.objects.filter(
        quantity_in_stock__lte=models.F('reorder_level')
    ).select_related('product', 'store').order_by('quantity_in_stock')
    
    if limit is not None:
        queryset = queryset[:limit]
    
    return queryset

def get_product_quantities_by_store(store_id, include_zero_stock=False):
    """
    Get product quantities for a specific store.
    
    Args:
        store_id (int): ID of the store to get inventory for
        include_zero_stock (bool): Whether to include products with zero stock. Default is False.
    
    Returns:
        QuerySet: Inventory objects for the specified store with product details
    """
    queryset = Inventory.objects.filter(
        store_id=store_id
    ).select_related('product', 'product__category', 'store')
    
    if not include_zero_stock:
        queryset = queryset.filter(quantity_in_stock__gt=0)
    
    return queryset.order_by('product__name')


def get_product_quantity_by_store_and_product(store_id, product_id):
    """
    Get quantity for a specific product in a specific store.
    
    Args:
        store_id (int): ID of the store
        product_id (int): ID of the product
    
    Returns:
        Inventory object or None if not found
    """
    try:
        return Inventory.objects.select_related('product', 'store').get(
            store_id=store_id,
            product_id=product_id
        )
    except Inventory.DoesNotExist:
        return None


def get_store_inventory_summary(store_id):
    """
    Get inventory summary for a specific store.
    
    Args:
        store_id (int): ID of the store
    
    Returns:
        dict: Summary with total products, low stock count, total value, etc.
    """
    
    inventory_queryset = Inventory.objects.filter(store_id=store_id).select_related('product')
    
    total_products = inventory_queryset.count()
    products_in_stock = inventory_queryset.filter(quantity_in_stock__gt=0).count()
    low_stock_count = inventory_queryset.filter(
        quantity_in_stock__lte=models.F('reorder_level'),
        quantity_in_stock__gt=0
    ).count()
    out_of_stock_count = inventory_queryset.filter(quantity_in_stock=0).count()
    
    # Calculate total inventory value using InventoryBatch model
    total_value = 0
    for inventory_item in inventory_queryset:
        # Get all batches for this product in this store with remaining quantity
        batches = InventoryBatch.objects.filter(
            product=inventory_item.product,
            store=inventory_item.store,
            quantity_remaining__gt=0
        ).order_by('created_at')  # FIFO order
        
        # Calculate value using weighted average or FIFO method
        item_value = sum([
            batch.quantity_remaining * batch.unit_cost
            for batch in batches
        ])
        total_value += item_value
    
    return {
        'total_products': total_products,
        'products_in_stock': products_in_stock,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'total_inventory_value': total_value,
        'stock_percentage': round((products_in_stock / total_products * 100) if total_products > 0 else 0, 2)
    }


def get_store_inventory_summary_optimized(store_id):
    """
    Optimized version using database aggregation for better performance.
    
    Args:
        store_id (int): ID of the store
    
    Returns:
        dict: Summary with total products, low stock count, total value, etc.
    """
    from app.models.transactions import InventoryBatch
    from django.db.models import Sum, F, Case, When, IntegerField
    
    inventory_queryset = Inventory.objects.filter(store_id=store_id).select_related('product')
    
    # Basic counts
    inventory_stats = inventory_queryset.aggregate(
        total_products=models.Count('id'),
        products_in_stock=Sum(
            Case(
                When(quantity_in_stock__gt=0, then=1),
                default=0,
                output_field=IntegerField()
            )
        ),
        low_stock_count=Sum(
            Case(
                When(
                    quantity_in_stock__lte=F('reorder_level'),
                    quantity_in_stock__gt=0,
                    then=1
                ),
                default=0,
                output_field=IntegerField()
            )
        ),
        out_of_stock_count=Sum(
            Case(
                When(quantity_in_stock=0, then=1),
                default=0,
                output_field=IntegerField()
            )
        )
    )
    
    # FIXED: Use the correct field name 'remaining_quantity'
    total_value = InventoryBatch.objects.filter(
        store_id=store_id,
        remaining_quantity__gt=0  # CORRECT FIELD NAME
    ).aggregate(
        total_value=Sum(F('remaining_quantity') * F('unit_cost'))  # CORRECT FIELD NAME
    )['total_value'] or 0
    
    total_products = inventory_stats['total_products'] or 0
    products_in_stock = inventory_stats['products_in_stock'] or 0
    stock_percentage = round((products_in_stock / total_products * 100) if total_products > 0 else 0, 2)
    low_stock_count = inventory_stats['low_stock_count'] or 0
    
    # STATUS CALCULATION
    if total_products == 0:
        status = 'No Stock'
    elif stock_percentage >= 95 and low_stock_count == 0:
        status = 'Excellent'
    elif stock_percentage >= 85:
        status = 'Good'
    elif stock_percentage >= 70:
        status = 'Fair'
    else:
        status = 'Poor'
    
    return {
        'total_products': total_products,
        'products_in_stock': products_in_stock,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': inventory_stats['out_of_stock_count'] or 0,
        'total_inventory_value': total_value,
        'stock_percentage': stock_percentage,
        'status': status,
    }



def get_product_inventory_value_by_store(store_id, product_id):
    """
    Calculate the total value of a specific product in a store using batch costs.
    
    Args:
        store_id (int): ID of the store
        product_id (int): ID of the product
    
    Returns:
        dict: Product inventory details with value breakdown
    """
    
    try:
        inventory_item = Inventory.objects.get(store_id=store_id, product_id=product_id)
    except Inventory.DoesNotExist:
        return {
            'product_id': product_id,
            'store_id': store_id,
            'quantity_in_stock': 0,
            'total_value': 0,
            'average_cost': 0,
            'batches': []
        }
    
    # Get all batches for this product in this store
    batches = InventoryBatch.objects.filter(
        product_id=product_id,
        store_id=store_id,
        remaining_quantity__gt=0  # CORRECT FIELD NAME
    ).order_by('created_at')
    
    # Calculate totals
    batch_data = []
    total_value = 0
    total_quantity = 0
    
    for batch in batches:
        batch_value = batch.remaining_quantity * batch.unit_cost  # CORRECT FIELD NAME
        total_value += batch_value
        total_quantity += batch.remaining_quantity  # CORRECT FIELD NAME
        
        batch_data.append({
            'batch_id': batch.id,
            'quantity': batch.remaining_quantity,  # CORRECT FIELD NAME
            'unit_cost': batch.unit_cost,
            'batch_value': batch_value,
            'purchase_date': batch.created_at,
            'supplier': batch.supplier.name if hasattr(batch, 'supplier') and batch.supplier else 'N/A'
        })
    
    average_cost = total_value / total_quantity if total_quantity > 0 else 0
    
    return {
        'product_id': product_id,
        'product_name': inventory_item.product.name,
        'store_id': store_id,
        'quantity_in_stock': inventory_item.quantity_in_stock,
        'total_value': total_value,
        'average_cost': average_cost,
        'batch_count': len(batch_data),
        'batches': batch_data
    }



def get_inventory_aging_report(store_id, days_threshold=90):
    """
    Get inventory aging report showing old stock that may need attention.
    
    Args:
        store_id (int): ID of the store
        days_threshold (int): Age threshold in days (default 90)
    
    Returns:
        QuerySet: InventoryBatch objects that are aging
    """
    from app.models.transactions import InventoryBatch
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days_threshold)
    
    aging_batches = InventoryBatch.objects.filter(
        store_id=store_id,
        remaining_quantity__gt=0,  # CORRECT FIELD NAME
        created_at__lt=cutoff_date
    ).select_related('product', 'store').order_by('created_at')
    
    return aging_batches




