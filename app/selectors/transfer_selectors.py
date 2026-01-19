from app.models.transactions import StockTransfer, StockTransferItem, TransferRequest
from django.db.models import *
from django.db.models.functions import Coalesce
from django.db.models import Case, When, F, DecimalField
from django.db.models import Subquery, OuterRef
from decimal import Decimal

def get_all_stock_transfers():
    return StockTransfer.objects.all()

def get_stock_transfer_by_id(transfer_id):
    return StockTransfer.objects.filter(id=transfer_id).first()

def get_stock_transfers_for_request(request_id):
    return StockTransfer.objects.filter(transfer_request_id=request_id)

def get_stock_transfer_items(transfer_id):
    return StockTransferItem.objects.filter(stock_transfer_id=transfer_id)

def get_total_quantity_transferred(product_id=None, from_date=None, to_date=None):
    qs = StockTransferItem.objects.all()
    if product_id:
        qs = qs.filter(product_id=product_id)
    if from_date:
        qs = qs.filter(stock_transfer__transfer_date__gte=from_date)
    if to_date:
        qs = qs.filter(stock_transfer__transfer_date__lte=to_date)
    return qs.aggregate(total=Sum('quantity'))['total'] or 0

def get_pending_transfer_requests():
    return TransferRequest.objects.filter(status='pending').order_by('-request_date')

def get_fulfilled_transfer_requests():
    return TransferRequest.objects.filter(status='fulfilled')

def get_approved_transfer_requests():
    return TransferRequest.objects.filter(status='approved')

def get_all_transfer_requests():
    return TransferRequest.objects.all()

def get_transfer_request_by_id(request_id):
    return TransferRequest.objects.filter(id=request_id).first()

def get_transfer_request_items(request_id):
    return StockTransferItem.objects.filter(stock_transfer__transfer_request_id=request_id)

def get_all_stock_transfer_items():
    return StockTransferItem.objects.all()

def get_stock_transfer_item_by_id(item_id):
    return StockTransferItem.objects.filter(id=item_id).first()




def get_transfer_requests_with_conversion_factors():
    """
    Get transfer requests with conversion factor calculations
    """
    from app.models.transactions import TransferRequest
    
    return TransferRequest.objects.annotate(
        total_base_units=Coalesce(
            Sum('items__base_quantity'),
            Value(0, output_field=IntegerField())
        ),
        total_items_count=Count('items'),
        has_conversion_issues=Case(
            When(
                Q(items__product__unit_prices__conversion_factor__lt=1) |
                Q(items__units__isnull=True),
                then=Value(True)
            ),
            default=Value(False),
            output_field=IntegerField()
        )
    ).prefetch_related(
        'items',
        'items__product',
        'items__units',
        'items__product__unit_prices'
    ).distinct()

def filter_transfer_requests_by_stock_availability(queryset, min_available=0):
    """
    Filter transfer requests by stock availability
    Returns requests where all items have sufficient stock
    """
    from app.models.transactions import TransferRequestItem
    from app.models.products import Inventory
    
    # Get requests where all items have sufficient stock
    requests_with_sufficient_stock = []
    
    for request in queryset:
        can_approve = True
        for item in request.items.all():
            try:
                inventory = Inventory.objects.get(
                    product=item.product,
                    store=request.from_store
                )
                if inventory.quantity_in_stock < item.base_quantity:
                    can_approve = False
                    break
            except Inventory.DoesNotExist:
                can_approve = False
                break
        
        if can_approve:
            requests_with_sufficient_stock.append(request.id)
    
    return queryset.filter(id__in=requests_with_sufficient_stock)

def filter_transfer_requests_by_conversion_type(queryset, conversion_type='all'):
    """
    Filter transfer requests by conversion type
    - 'simple': All items use base units (CF = 1)
    - 'complex': Some items use conversion factors (CF > 1)
    - 'mixed': Mix of base and converted units
    """
    from app.models.transactions import TransferRequestItem
    from app.models.products import ProductUnitPrice
    
    if conversion_type == 'simple':
        # All items use base units
        return queryset.filter(
            items__product__unit_prices__conversion_factor=1
        ).exclude(
            items__product__unit_prices__conversion_factor__gt=1
        ).distinct()
    
    elif conversion_type == 'complex':
        # Some items use conversion factors > 1
        return queryset.filter(
            items__product__unit_prices__conversion_factor__gt=1
        ).distinct()
    
    elif conversion_type == 'mixed':
        # Mix of base and converted units
        has_base = queryset.filter(
            items__product__unit_prices__conversion_factor=1
        ).values('id')
        
        has_converted = queryset.filter(
            items__product__unit_prices__conversion_factor__gt=1
        ).values('id')
        
        # Get requests that appear in both lists
        mixed_ids = set(h['id'] for h in has_base) & set(h['id'] for h in has_converted)
        return queryset.filter(id__in=mixed_ids)
    
    return queryset

def filter_transfer_requests_by_base_units(queryset, min_units=None, max_units=None):
    """
    Filter transfer requests by total base units
    """
    queryset = queryset.annotate(
        total_base=Coalesce(
            Sum('items__base_quantity'),
            Value(0, output_field=IntegerField())
        )
    )
    
    if min_units is not None:
        queryset = queryset.filter(total_base__gte=min_units)
    
    if max_units is not None:
        queryset = queryset.filter(total_base__lte=max_units)
    
    return queryset

def filter_transfer_requests_by_product_category(queryset, category_id):
    """
    Filter transfer requests by product category
    """
    return queryset.filter(
        items__product__category__id=category_id
    ).distinct()

def filter_transfer_requests_by_unit_type(queryset, unit_id):
    """
    Filter transfer requests by unit type
    """
    return queryset.filter(
        items__units__id=unit_id
    ).distinct()

def get_pending_transfer_requests_with_low_stock():
    """
    Get pending transfer requests with low stock availability
    """
    from app.models.transactions import TransferRequest
    from app.models.products import Inventory
    
    pending_requests = TransferRequest.objects.filter(status='pending')
    
    low_stock_requests = []
    for request in pending_requests:
        has_low_stock = False
        for item in request.items.all():
            try:
                inventory = Inventory.objects.get(
                    product=item.product,
                    store=request.from_store
                )
                # Check if available stock is less than requested base units
                if inventory.quantity_in_stock < item.base_quantity:
                    has_low_stock = True
                    break
            except Inventory.DoesNotExist:
                has_low_stock = True
                break
        
        if has_low_stock:
            low_stock_requests.append(request.id)
    
    return TransferRequest.objects.filter(id__in=low_stock_requests)

def get_transfer_requests_by_conversion_factor_range(queryset, min_cf=None, max_cf=None):
    """
    Filter transfer requests by conversion factor range
    """
    if min_cf is not None or max_cf is not None:
        from app.models.transactions import TransferRequestItem
        from app.models.products import ProductUnitPrice
        
        # Get item IDs with conversion factor in range
        item_filter = Q()
        
        if min_cf is not None:
            item_filter &= Q(
                product__unit_prices__conversion_factor__gte=min_cf
            )
        
        if max_cf is not None:
            item_filter &= Q(
                product__unit_prices__conversion_factor__lte=max_cf
            )
        
        item_ids = TransferRequestItem.objects.filter(item_filter).values_list('id', flat=True)
        
        # Get requests containing these items
        return queryset.filter(items__id__in=item_ids).distinct()
    
    return queryset

def filter_transfer_requests_with_conversion_errors(queryset):
    """
    Filter transfer requests that have conversion factor errors
    """
    from app.models.transactions import TransferRequestItem
    
    # Get items without conversion factors
    items_without_cf = TransferRequestItem.objects.filter(
        product__unit_prices__unit=OuterRef('units')
    ).filter(
        product__unit_prices__isnull=True
    ).values('id')
    
    # Get requests containing these items
    return queryset.filter(
        items__in=Subquery(items_without_cf)
    ).distinct()
