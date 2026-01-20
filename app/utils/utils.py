# app/helpers/conversion.py
from decimal import Decimal, ROUND_DOWN
from django.core.exceptions import ValidationError
from app.models.products import ProductUnitPrice

def convert_to_base_units(product, unit, quantity):
    """
    Convert UI quantity to base units.
    Returns an INTEGER Decimal representing base units.
    Raises ValidationError if conversion factor missing or results in fractional units.
    """
    try:
        product_unit = ProductUnitPrice.objects.get(product=product, unit=unit)
    except ProductUnitPrice.DoesNotExist:
        raise ValidationError(
            f"No conversion factor defined for {product.name} with unit {unit.name}"
        )

    base_qty = Decimal(quantity) * Decimal(product_unit.conversion_factor)

    if base_qty % 1 != 0:
        raise ValidationError(
            f"Conversion resulted in fractional base units for {product.name} "
            f"({quantity} {unit.name} x CF {product_unit.conversion_factor} = {base_qty})"
        )

    return int(base_qty)  # Always store base units as integer

def convert_from_base_units(product, unit, base_quantity):
    """
    Convert from base units to a display unit.
    Returns Decimal rounded to 4 decimal places.
    """
    try:
        product_unit = ProductUnitPrice.objects.get(product=product, unit=unit)
        if product_unit.conversion_factor == 0:
            return Decimal(0)
        return (Decimal(base_quantity) / Decimal(product_unit.conversion_factor)).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
    except ProductUnitPrice.DoesNotExist:
        return Decimal(base_quantity)

def validate_conversion_factor_exists(product, unit):
    """
    Validate that a conversion factor exists for this product-unit.
    Raises ValidationError if missing.
    """
    if not ProductUnitPrice.objects.filter(product=product, unit=unit).exists():
        raise ValidationError(
            f"No conversion factor defined for {product.name} with unit {unit.name}. "
            f"Please define it in product settings first."
        )



def get_base_unit_price(product):
    base = product.unit_prices.filter(conversion_factor=1).first()
    if not base:
        raise ValueError(f"No base price defined for {product}")
    return base.price


def get_unit_price(product, unit):
    """
    ALWAYS derived from base unit price
    """
    base_price = get_base_unit_price(product)

    unit_price = product.unit_prices.filter(unit=unit).first()
    if not unit_price:
        raise ValueError(f"No conversion factor for {product} / {unit}")

    return base_price * unit_price.conversion_factor
