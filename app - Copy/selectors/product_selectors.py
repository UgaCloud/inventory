from app.models.products import Product

def get_all_products():
    return Product.objects.all()

def get_product_by_id(product_id):
    return Product.objects.get(id = product_id)