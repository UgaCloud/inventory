from app.models.products import Category

def get_category_by_id(category_id):
    return Category.objects.get(id = category_id)

def get_all_categories():
    return Category.objects.all()