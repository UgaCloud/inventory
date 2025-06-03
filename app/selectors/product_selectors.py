from app.models.products import Product, Category, UnitOfMeasure

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