# app/templatetags/custom_filters.py
from django import template
from datetime import timedelta
from django.template.defaultfilters import stringfilter




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
























