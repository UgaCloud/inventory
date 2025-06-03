from django.forms import ModelForm
from app.models.products import Product, Category, UnitOfMeasure, ProductUnitPrice

class UnitOfMeasureForm(ModelForm):
    class Meta:
        model = UnitOfMeasure
        fields = ("__all__")

class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = ("__all__")

class CategoryForm(ModelForm):
    class Meta:
        model = Category
        fields = ("__all__")

class ProductUnitPriceForm(ModelForm):
    class Meta:
        model = ProductUnitPrice
        fields = ("__all__")

