def generate_sku(product_name, brand_name, category_name):
    """
    Auto-generates SKU if not provided, based on category and a sequence
    """
    prefix = (category_name[:3].upper())
    
    last_product = Product.objects.filter(category=category).order_by('-id').first()
    
    if last_product and last_product.sku and last_product.sku.startswith(prefix):
        # Extract numeric part and increment
        match = re.search(rf"{prefix}(\d+)", last_product.sku)
        
        if match:
            next_num = int(match.group(1)) + 1
        else:
            next_num = 1
    else:
        next_num = 1
    
    sku = f"{prefix}{next_num:04d}"
    
    return sku