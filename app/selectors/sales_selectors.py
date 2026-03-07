from django.db.models import Sum, F
from app.models.transactions import Sales, SalesItem


def get_all_sales_per_date(user=None):
    qs = Sales.objects.all().order_by("-sale_date")
    if user:
        qs = qs.filter(recorded_by=user)
    return qs





def get_sale_by_id(sale_id, user=None):
    qs = Sales.objects.filter(pk=sale_id)
    if user:
        qs = qs.filter(recorded_by=user)
    return qs.first()


def get_sales_for_customer(customer_id, user=None):
    qs = Sales.objects.filter(customer_id=customer_id)
    if user:
        qs = qs.filter(recorded_by=user)
    return qs.order_by("-sale_date")


def get_sales_items_for_sale(sale):
    if isinstance(sale, int):
        return SalesItem.objects.filter(order_id=sale)
    return SalesItem.objects.filter(order=sale)


def get_total_sales(user=None):
    qs = Sales.objects.all()
    if user:
        qs = qs.filter(recorded_by=user)

    return qs.aggregate(
        total=Sum(F("items__quantity") * F("items__sale_price"))
    )["total"] or 0


def get_total_items_sold(user=None):
    qs = SalesItem.objects.all()
    if user:
        qs = qs.filter(order__recorded_by=user)
    return qs.aggregate(total=Sum("quantity"))["total"] or 0


def get_sales_in_date_range(start_date, end_date, user=None):
    qs = Sales.objects.filter(sale_date__range=[start_date, end_date])
    if user:
        qs = qs.filter(recorded_by=user)
    return qs.order_by("-sale_date")


def get_recent_sales(user=None, limit=5):
    qs = Sales.objects.all().order_by("-sale_date")
    if user:
        qs = qs.filter(recorded_by=user)
    return qs[:limit]


def get_top_selling_products(limit=10, user=None):
    qs = SalesItem.objects.select_related("product")

    if user:
        qs = qs.filter(order__recorded_by=user)

    return (
        qs.values("product__id", "product__name")
        .annotate(total_sold=Sum("quantity"))
        .order_by("-total_sold")[:limit]
    )
