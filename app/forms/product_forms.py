from django.forms import ModelForm, HiddenInput
from app.models.products import Product, Category, UnitOfMeasure, ProductUnitPrice, Inventory, StoreLocation

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
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['product'].widget=HiddenInput()

class InventoryForm(ModelForm):
    class Meta:
        model = Inventory
        fields = ("__all__")

class StoreLocationForm(ModelForm):
    class Meta:
        model = StoreLocation
        fields = ("__all__")
