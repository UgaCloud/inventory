from app.models.products import Product, Category, UnitOfMeasure, ProductUnitPrice, Inventory

#product selectors
def get_all_products():
    return Product.objects.all()

def get_product_by_id(product_id):
    return Product.objects.get(id = product_id)

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

# Inventory selectors
def get_all_products_in_inventory():
    return Inventory.objects.all()
