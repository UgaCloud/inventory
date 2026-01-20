# app/templatetags/custom_filters.py
from django import template
from datetime import timedelta
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from decimal import Decimal, ROUND_DOWN





register = template.Library()

@register.filter
def is_list(value):
    return isinstance(value, list)

@register.filter
def is_dict(value):
    return isinstance(value, dict)


@register.filter
def divide(value, arg):
    """Divide value by arg"""
    try:
        if value is None or arg is None or arg == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        if value is None or arg is None:
            return 0
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        if value is None:
            return 0
        if arg is None:
            return float(value)
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value or 0

@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        if total == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError):
        return 0

@register.filter
def safe_int(value):
    """Safely convert to integer"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
    
@register.filter
def get_rank_badge(rank):
    """Return badge class based on rank"""
    if rank == 1:
        return 'success'
    elif rank == 2:
        return 'info'
    elif rank == 3:
        return 'warning'
    else:
        return 'secondary'
    
@register.filter
def dict_lookup(dict_list, index):
    """Get item from list of dictionaries by index"""
    try:
        return dict_list[index]
    except (IndexError, TypeError):
        return {}




@register.filter
def div(value, arg):
    """Divide the value by the argument"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sum_attr(items, attr):
    """Sum values of an attribute from a list of objects"""
    total = 0
    for item in items:
        value = getattr(item, attr, 0)
        try:
            total += float(value)
        except (ValueError, TypeError):
            pass
    return total

@register.filter
def add_days(date, days):
    """Add days to a date"""
    try:
        return date + timedelta(days=int(days))
    except (ValueError, TypeError):
        return date
    

@register.filter(name='abs')
def absolute_value(value):
    """Return absolute value"""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return value

@register.filter
def map_attr(value, arg):
    """Map an attribute from a list of objects"""
    if not value:
        return []
    try:
        return [getattr(item, arg) for item in value]
    except (AttributeError, TypeError):
        return []

@register.filter
def sum_list(value):
    """Sum a list of values"""
    if not value:
        return 0
    try:
        return sum([float(v) for v in value])
    except (ValueError, TypeError):
        return 0
    


@register.filter
def get_store_color_hex(report):
    """Get store color hex code based on store name"""
    store_name = report['store'].name.lower()
    if 'kampala' in store_name:
        return '#4A90E2'
    elif 'entebbe' in store_name:
        return '#36B9CC'
    elif 'jinja' in store_name:
        return '#1CC88A'
    elif 'gulu' in store_name:
        return '#F6C23E'
    elif 'mbarara' in store_name:
        return '#E74A3B'
    else:
        return '#6C757D'


@register.filter
def sum_total_units(reports):
    """Sum total units across all stores"""
    if not reports:
        return 0
    return sum(report.get('total_units', 0) for report in reports)

@register.filter
def max_utilization_store(reports):
    """Get store with maximum utilization"""
    if not reports:
        return "N/A"
    max_report = max(reports, key=lambda x: x.get('utilization_percentage', 0))
    return f"{max_report['store'].name} ({max_report.get('utilization_percentage', 0)}%)"

@register.filter
def min_utilization_store(reports):
    """Get store with minimum utilization"""
    if not reports:
        return "N/A"
    min_report = min(reports, key=lambda x: x.get('utilization_percentage', 0))
    return f"{min_report['store'].name} ({min_report.get('utilization_percentage', 0)}%)"

@register.filter
def max_activity_store(reports):
    """Get store with maximum activity"""
    if not reports:
        return "N/A"
    max_report = max(reports, key=lambda x: x.get('recent_activity', 0))
    return max_report['store'].name

@register.filter
def avg_transaction_value(reports):
    """Calculate average transaction value across all stores"""
    if not reports:
        return 0
    total_sales = sum(report.get('sales_data', {}).get('total_sales', 0) or 0 for report in reports)
    total_transactions = sum(report.get('sales_data', {}).get('total_transactions', 0) or 0 for report in reports)
    if total_transactions == 0:
        return 0
    return int(total_sales / total_transactions)

@register.filter
def total_transactions(reports):
    """Total transactions across all stores"""
    if not reports:
        return 0
    return sum(report.get('sales_data', {}).get('total_transactions', 0) or 0 for report in reports)

@register.filter
def most_improved_store(reports):
    """Get store with highest growth rate"""
    if not reports:
        return "N/A"
    max_report = max(reports, key=lambda x: x.get('growth_rate', 0))
    return f"{max_report['store'].name} ({max_report.get('growth_rate', 0)}%)"

@register.filter
def max_score_store(reports):
    """Get store with maximum performance score"""
    if not reports:
        return "N/A"
    max_report = max(reports, key=lambda x: x.get('performance_score', 0))
    return max_report['store'].name

@register.filter
def max_score_value(reports):
    """Get maximum performance score value"""
    if not reports:
        return 0
    return max(report.get('performance_score', 0) for report in reports)

@register.filter
def avg_score(reports):
    """Calculate average performance score"""
    if not reports:
        return 0
    total = sum(report.get('performance_score', 0) for report in reports)
    return total / len(reports)

@register.filter
def min_sales(reports):
    """Get minimum sales value"""
    if not reports:
        return 0
    return min(report.get('sales_data', {}).get('total_sales', 0) or 0 for report in reports)

@register.filter
def max_sales(reports):
    """Get maximum sales value"""
    if not reports:
        return 0
    return max(report.get('sales_data', {}).get('total_sales', 0) or 0 for report in reports)

@register.filter
def avg_utilization_excluding(reports, store_id):
    """Calculate average utilization excluding a specific store"""
    if not reports:
        return 0
    
    # Convert store_id to int if it's a string
    try:
        store_id = int(store_id)
    except (ValueError, TypeError):
        return 0
    
    filtered_reports = [r for r in reports if r['store'].id != store_id]
    if not filtered_reports:
        return 0
    
    total = sum(report.get('utilization_percentage', 0) for report in filtered_reports)
    return total / len(filtered_reports)

@register.filter
def avg_transaction_excluding(reports, store_id):
    """Calculate average transaction value excluding a specific store"""
    if not reports:
        return 0
    
    # Convert store_id to int if it's a string
    try:
        store_id = int(store_id)
    except (ValueError, TypeError):
        return 0
    
    filtered_reports = [r for r in reports if r['store'].id != store_id]
    if not filtered_reports:
        return 0
    
    total_sales = sum(report.get('sales_data', {}).get('total_sales', 0) or 0 for report in filtered_reports)
    total_transactions = sum(report.get('sales_data', {}).get('total_transactions', 0) or 0 for report in filtered_reports)
    if total_transactions == 0:
        return 0
    
    return int(total_sales / total_transactions)

@register.filter
def avg_score_excluding(reports, store_id):
    """Calculate average score excluding a specific store"""
    if not reports:
        return 0
    
    # Convert store_id to int if it's a string
    try:
        store_id = int(store_id)
    except (ValueError, TypeError):
        return 0
    
    filtered_reports = [r for r in reports if r['store'].id != store_id]
    if not filtered_reports:
        return 0
    
    total = sum(report.get('performance_score', 0) for report in filtered_reports)
    return total / len(filtered_reports)

@register.filter
def divide(value, arg):
    """Divide the value by arg"""
    try:
        value_float = float(value) if value is not None else 0
        arg_float = float(arg) if arg is not None else 0
        if arg_float == 0:
            return 0
        return value_float / arg_float
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        value_float = float(value) if value is not None else 0
        arg_float = float(arg) if arg is not None else 0
        return value_float - arg_float
    except (ValueError, TypeError):
        return 0
    
@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        value_float = float(value) if value is not None else 0
        arg_float = float(arg) if arg is not None else 0
        return value_float * arg_float
    except (ValueError, TypeError):
        return 0

@register.filter
def add_percentage(value, percentage):
    """Add percentage to value"""
    try:
        value_float = float(value) if value is not None else 0
        percentage_float = float(percentage) if percentage is not None else 0
        return value_float * (1 + percentage_float / 100)
    except (ValueError, TypeError):
        return value

@register.filter
def percentage_difference(value1, value2):
    """Calculate percentage difference between two values"""
    try:
        val1 = float(value1) if value1 is not None else 0
        val2 = float(value2) if value2 is not None else 0
        if val2 == 0:
            return 0
        return ((val1 - val2) / val2) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def get_default_store_report(reports):
    """Get the report for the default store"""
    for report in reports:
        if report['store'].is_default:
            return report
    return None


@register.filter
def get_item(dictionary, key):
    """Template filter to get dictionary item by key"""
    return dictionary.get(key)



# app/templatetags/transfer_filters.py


@register.filter
def format_conversion_factor(value, product_unit=None):
    """
    Format conversion factor for display
    Example: 10.0000 -> "CF: 10.0000"
    """
    if value is None:
        return "CF: 1.0000"
    
    try:
        cf = Decimal(value)
        if cf == 1:
            return mark_safe('<span class="badge bg-success">Base Unit</span>')
        elif cf.is_integer():
            return f"CF: {int(cf)}"
        else:
            return f"CF: {cf.quantize(Decimal('0.0001'), rounding=ROUND_DOWN)}"
    except:
        return "CF: 1.0000"

@register.filter
def calculate_base_units(quantity, conversion_factor):
    """
    Calculate base units from quantity and conversion factor
    Returns: QTY × CF = Result
    """
    if quantity is None or conversion_factor is None:
        return "0"
    
    try:
        qty = Decimal(str(quantity))
        cf = Decimal(str(conversion_factor))
        result = qty * cf
        
        if result.is_integer():
            result_str = str(int(result))
        else:
            result_str = str(result.quantize(Decimal('0.0001'), rounding=ROUND_DOWN))
        
        return mark_safe(f'<span class="calculation-highlight">{qty} × {cf} = {result_str}</span>')
    except:
        return "0"

@register.filter
def format_quantity_with_unit(quantity, unit):
    """
    Format quantity with unit abbreviation
    """
    if not quantity:
        return "0"
    
    if hasattr(unit, 'abbreviation'):
        return f"{quantity} {unit.abbreviation}"
    elif unit and hasattr(unit, 'name'):
        return f"{quantity} {unit.name}"
    else:
        return f"{quantity} units"

@register.filter
def get_conversion_explanation(unit, product):
    """
    Get conversion explanation for a unit
    """
    if not unit or not product:
        return ""
    
    try:
        # Get base unit for this product
        base_unit = product.unit_prices.filter(conversion_factor=1).first()
        if not base_unit:
            return ""
        
        # Get conversion factor for this unit
        unit_price = product.unit_prices.filter(unit=unit).first()
        if not unit_price:
            return ""
        
        cf = unit_price.conversion_factor
        base_unit_name = base_unit.unit.abbreviation or base_unit.unit.name
        
        if cf == 1:
            return f"Base unit ({base_unit_name})"
        else:
            return f"1 {unit.abbreviation} = {cf} {base_unit_name}"
    except:
        return ""

@register.filter
def dict_key(dictionary, key):
    """
    Get value from dictionary by key in template
    """
    if dictionary and key in dictionary:
        return dictionary[key]
    return None

@register.filter
def can_approve_request(request):
    """
    Check if a transfer request can be approved
    """
    if not hasattr(request, 'can_approve'):
        return False
    return request.can_approve

@register.filter
def get_stock_availability(item, store):
    """
    Get stock availability for an item in a store
    """
    if not item or not store:
        return 0
    
    try:
        from app.models.products import Inventory
        inventory = Inventory.objects.filter(
            product=item.product,
            store=store
        ).first()
        return inventory.quantity_in_stock if inventory else 0
    except:
        return 0

@register.filter
def calculate_shortage(request_item):
    """
    Calculate shortage for a request item
    """
    if not hasattr(request_item, 'transfer_request'):
        return 0
    
    try:
        available = request_item.get_available_stock()
        shortage = request_item.base_quantity - available
        return max(0, shortage)
    except:
        return 0

@register.filter
def get_conversion_summary(request):
    """
    Get conversion summary for a transfer request
    """
    if not hasattr(request, 'conversion_factor_summary'):
        return ""
    
    summary = request.conversion_factor_summary
    # Truncate for display
    if len(summary) > 150:
        return summary[:150] + "..."
    return summary

@register.filter
def format_conversion_calculation(item):
    """
    Format conversion calculation for an item
    """
    if not hasattr(item, 'qty_x_cf_calculation'):
        return ""
    return item.qty_x_cf_calculation

@register.filter
def get_base_unit_name(product):
    """
    Get base unit name for a product
    """
    if not hasattr(product, 'unit_prices'):
        return "base units"
    
    try:
        base_unit = product.unit_prices.filter(conversion_factor=1).first()
        if base_unit and base_unit.unit:
            return base_unit.unit.name
        return "base units"
    except:
        return "base units"


















