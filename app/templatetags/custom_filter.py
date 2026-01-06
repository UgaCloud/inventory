# app/templatetags/custom_filters.py
from django import template
from datetime import timedelta


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
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    