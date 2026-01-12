from decimal import Decimal
from django.core.exceptions import ValidationError
from app.models.products import ProductUnitPrice

def convert_to_base_units(product, unit, quantity):
    """Convert quantity from any unit to base units"""
    try:
        product_unit = ProductUnitPrice.objects.get(product=product, unit=unit)
        return Decimal(quantity) * Decimal(product_unit.conversion_factor)
    except ProductUnitPrice.DoesNotExist:
        return Decimal(quantity)

def convert_from_base_units(product, unit, base_quantity):
    """Convert from base units to specific unit"""
    try:
        product_unit = ProductUnitPrice.objects.get(product=product, unit=unit)
        if product_unit.conversion_factor == 0:
            return Decimal(0)
        return Decimal(base_quantity) / Decimal(product_unit.conversion_factor)
    except ProductUnitPrice.DoesNotExist:
        return Decimal(base_quantity)

def validate_conversion_factor_exists(product, unit):
    """Validate that a conversion factor exists for this product-unit"""
    if not ProductUnitPrice.objects.filter(product=product, unit=unit).exists():
        raise ValidationError(
            f"No conversion factor defined for {product.name} with unit {unit.name}. "
            f"Please define the unit price and conversion factor in product settings first."
        )