from app.models.products import Product, Category, UnitOfMeasure, ProductUnitPrice, Inventory, StoreLocation
from django.db import models

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


