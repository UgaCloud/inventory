from django.forms import ModelForm
from django import forms
from app.models.products import Product, Category, UnitOfMeasure

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

