"""Operational metrics for the dashboards.

Every number a dashboard shows is computed here from the tenant's own rows.
Nothing is hard-coded: a business with no activity gets zeros, and the
templates render the honest empty state instead of a decorative placeholder.

All querysets go through the tenant-aware managers, so the metrics are
scoped to the signed-in user's business without extra plumbing.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum

from app.models.customers import Customer
from app.models.expense import Expense
from app.models.products import Inventory, Product, StoreLocation
from app.models.transactions import (
    InventoryBatch,
    PurchaseOrder,
    Sales,
    SalesItem,
    StockAdjustment,
    StockMovement,
    StockTransfer,
    TransferRequest,
)

# A sale is considered overdue once it is this old and still unpaid.
OVERDUE_DAYS = 30
# Stock movement types that add stock.
INBOUND_MOVEMENTS = ("In", "Stocked", "Initial Stock")


def _num(value):
    """Return a plain number for a possibly ``None``/``Decimal`` aggregate."""
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return float(value)
    return value


def _pct(numerator, denominator):
    """Percentage of ``numerator`` over ``denominator`` (0 when undefined)."""
    numerator = _num(numerator)
    denominator = _num(denominator)
    if not denominator:
        return 0
    return round(numerator / denominator * 100, 1)


def _change_pct(current, previous):
    """Month-over-month change in percent; ``None`` when there is no baseline."""
    current = _num(current)
    previous = _num(previous)
    if previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def _month_bounds(anchor=None):
    """Return ``(first_day, last_day)`` of the month owning ``anchor``."""
    anchor = anchor or date.today()
    first = anchor.replace(day=1)
    if first.month == 12:
        nxt = first.replace(year=first.year + 1, month=1)
    else:
        nxt = first.replace(month=first.month + 1)
    return first, nxt - timedelta(days=1)


# ---------------------------------------------------------------------------
# Sales dashboard
# ---------------------------------------------------------------------------

def get_sales_dashboard_metrics(user=None, today=None):
    """The operational numbers the sales dashboard renders.

    ``user`` scopes the "my activity" cards (today's sales, collections);
    tenant-wide figures (outstanding balances, overdue) stay business-wide
    because somebody has to chase them.
    """
    today = today or date.today()
    week_start = today - timedelta(days=6)
    month_start, month_end = _month_bounds(today)

    mine = Sales.objects.filter(is_cancelled=False)
    if user is not None and getattr(user, "is_authenticated", False):
        mine = mine.filter(recorded_by=user)
    else:
        mine = mine.none()

    all_sales = Sales.objects.filter(is_cancelled=False)

    # -- balances ---------------------------------------------------------
    total_outstanding_balances = all_sales.aggregate(t=Sum("balance"))["t"] or 0

    overdue_qs = all_sales.filter(
        balance__gt=0, sale_date__lte=today - timedelta(days=OVERDUE_DAYS)
    ).select_related("customer")
    overdue_payments = [
        {
            "receipt_no": sale.receipt_no,
            "customer": sale.customer.name if sale.customer else "Walk-in Customer",
            "balance": sale.balance,
            "days_overdue": (today - sale.sale_date).days,
        }
        for sale in overdue_qs.order_by("sale_date")
    ]
    total_overdue_amount = sum(item["balance"] for item in overdue_payments)

    # -- today ------------------------------------------------------------
    today_sales = mine.filter(sale_date=today)
    today_totals = today_sales.aggregate(
        total=Sum("total_amount"), received=Sum("amount_received")
    )
    today_sales_total = _num(today_totals["total"])
    today_received = _num(today_totals["received"])
    today_payment_percentage = _pct(today_received, today_sales_total)

    credit_sales = today_sales.filter(balance__gt=0)
    today_credit_count = credit_sales.count()
    todays_credit_sales = credit_sales.aggregate(t=Sum("total_amount"))["t"] or 0

    unpaid = today_sales.filter(amount_received=0)
    unpaid_totals = unpaid.aggregate(
        count=Count("id"), total_amount=Sum("total_amount")
    )
    todays_unpaid_sales = {
        "count": unpaid_totals["count"] or 0,
        "total_amount": unpaid_totals["total_amount"] or 0,
    }

    # -- week / month -----------------------------------------------------
    # Week and month figures are business-wide: they describe how the
    # business is doing, not one person's book.
    weekly_totals = all_sales.filter(
        sale_date__gte=week_start, sale_date__lte=today
    ).aggregate(total=Sum("total_amount"), received=Sum("amount_received"))
    weekly_sales = _num(weekly_totals["total"])
    weekly_payments = _num(weekly_totals["received"])

    monthly_totals = all_sales.filter(
        sale_date__gte=month_start, sale_date__lte=month_end
    ).aggregate(total=Sum("total_amount"), received=Sum("amount_received"))
    monthly_sales = _num(monthly_totals["total"])
    monthly_payments = _num(monthly_totals["received"])

    # Collection rate achieved so far this month (a real ratio, not a goal).
    collection_target_percentage = _pct(monthly_payments, monthly_sales)
    collection_progress = min(collection_target_percentage, 100)

    # -- efficiency & ageing ---------------------------------------------
    last_30 = all_sales.filter(sale_date__gte=today - timedelta(days=29))
    last_30_count = last_30.count()
    last_30_paid = last_30.filter(balance=0).count()
    payment_efficiency = _pct(last_30_paid, last_30_count)

    outstanding = all_sales.filter(balance__gt=0)
    outstanding_count = outstanding.count()
    if outstanding_count:
        outstanding_ages = [
            (today - sale.sale_date).days for sale in outstanding.only("sale_date")
        ]
        average_days_outstanding = round(sum(outstanding_ages) / outstanding_count)
    else:
        average_days_outstanding = 0

    customers_with_balance = Customer.objects.filter(balance__gt=0).count()

    top_outstanding_customers = [
        {
            "name": customer.name,
            "phone": customer.phone or "",
            "balance": _num(customer.balance),
        }
        for customer in Customer.objects.filter(balance__gt=0).order_by("-balance")[:5]
    ]

    return {
        "total_outstanding_balances": total_outstanding_balances,
        "today_payment_percentage": today_payment_percentage,
        "todays_credit_sales": todays_credit_sales,
        "today_credit_count": today_credit_count,
        "todays_unpaid_sales": todays_unpaid_sales,
        "weekly_sales": weekly_sales,
        "weekly_payments": weekly_payments,
        "monthly_sales": monthly_sales,
        "monthly_payments": monthly_payments,
        "collection_target_percentage": collection_target_percentage,
        "collection_progress": collection_progress,
        "payment_efficiency": payment_efficiency,
        "average_days_outstanding": average_days_outstanding,
        "customers_with_balance": customers_with_balance,
        "top_outstanding_customers": top_outstanding_customers,
        "overdue_payments": overdue_payments,
        "total_overdue_amount": total_overdue_amount,
    }


# ---------------------------------------------------------------------------
# Stores dashboard
# ---------------------------------------------------------------------------

def get_default_store():
    """The store a storekeeper is most likely working in."""
    store = StoreLocation.objects.filter(is_default=True, is_active=True).first()
    if store is None:
        store = StoreLocation.objects.filter(is_active=True).first()
    return store


def get_recent_activities(limit=6):
    """A merged timeline of the latest stock and sales activity."""
    activities = []

    for movement in StockMovement.objects.select_related("product")[:limit * 2]:
        activities.append(
            {
                "type": "transfer",
                "description": (
                    f"{movement.product.name}: {movement.transaction_type} "
                    f"({movement.quantity:+d} units) at {movement.store.name}"
                ),
                "timestamp": movement.timestamp,
            }
        )

    for adjustment in StockAdjustment.objects.select_related("product")[:limit * 2]:
        activities.append(
            {
                "type": "adjustment",
                "description": (
                    f"{adjustment.product.name}: stock adjustment "
                    f"({adjustment.quantity_change:+d} units)"
                ),
                "timestamp": adjustment.created_at,
            }
        )

    for sale in Sales.objects.filter(is_cancelled=False).select_related("customer")[:limit * 2]:
        activities.append(
            {
                "type": "sale",
                "description": (
                    f"Sale #{sale.receipt_no} — "
                    f"{sale.customer.name if sale.customer else 'Walk-in Customer'} "
                    f"({_num(sale.total_amount):,.0f})"
                ),
                "timestamp": sale.created_at,
            }
        )

    activities.sort(key=lambda item: item["timestamp"], reverse=True)
    return activities[:limit]


def get_stores_dashboard_metrics(user=None, today=None):
    """The operational numbers the stores dashboard renders."""
    today = today or date.today()
    week_start = today - timedelta(days=6)
    month_start = today - timedelta(days=29)

    low_stock = Inventory.objects.filter(quantity_in_stock__lte=F("reorder_level"))
    low_stock_count = low_stock.count()

    pending_transfers = StockTransfer.objects.filter(status="pending").count()
    pending_transfer_requests = TransferRequest.objects.filter(status="pending").count()

    today_sales = Sales.objects.filter(
        sale_date=today, is_cancelled=False
    ).aggregate(t=Sum("total_amount"))["t"] or 0
    sales_count_today = Sales.objects.filter(
        sale_date=today, is_cancelled=False
    ).count()

    weekly_sales = Sales.objects.filter(
        sale_date__gte=week_start, sale_date__lte=today, is_cancelled=False
    ).aggregate(t=Sum("total_amount"))["t"] or 0

    # Units received today and the value that came in with them.
    received_movements = StockMovement.objects.filter(
        timestamp__date=today, transaction_type__in=INBOUND_MOVEMENTS
    )
    stock_received_today = sum(m.quantity for m in received_movements)
    stock_received_value = InventoryBatch.objects.filter(
        created_at__date=today
    ).aggregate(t=Sum(F("remaining_quantity") * F("unit_cost")))["t"] or 0

    # Units sold today and the products that moved.
    sold_items = SalesItem.objects.filter(
        order__sale_date=today, order__is_cancelled=False
    )
    stock_sold_today = sold_items.aggregate(t=Sum("quantity"))["t"] or 0
    top_moving_products = [
        {
            "product__name": row["product__name"],
            "total_sold": row["total_sold"],
        }
        for row in sold_items.values("product__name")
        .annotate(total_sold=Sum("quantity"))
        .order_by("-total_sold")[:3]
    ]

    # Inventory value and turnover.
    total_inventory_value = InventoryBatch.objects.filter(
        remaining_quantity__gt=0
    ).aggregate(t=Sum(F("remaining_quantity") * F("unit_cost")))["t"] or 0
    units_in_stock = Inventory.objects.aggregate(t=Sum("quantity_in_stock"))["t"] or 0
    units_sold_30d = SalesItem.objects.filter(
        order__sale_date__gte=month_start,
        order__sale_date__lte=today,
        order__is_cancelled=False,
    ).aggregate(t=Sum("quantity"))["t"] or 0
    stock_turnover_rate = round(units_sold_30d / units_in_stock, 2) if units_in_stock else 0

    daily_customers = (
        Sales.objects.filter(sale_date=today, is_cancelled=False)
        .exclude(customer=None)
        .values("customer")
        .distinct()
        .count()
    )

    my_transfer_requests = []
    if user is not None and getattr(user, "is_authenticated", False):
        my_transfer_requests = list(
            TransferRequest.objects.filter(requested_by=user)
            .prefetch_related("items")
            .order_by("-request_date")[:5]
        )

    metrics = {
        "low_stock_count": low_stock_count,
        "pending_transfers": pending_transfers,
        "pending_transfer_requests": pending_transfer_requests,
        "today_sales": today_sales,
        "sales_count_today": sales_count_today,
        "weekly_sales": weekly_sales,
        "stock_received_today": stock_received_today,
        "stock_received_value": stock_received_value,
        "stock_sold_today": stock_sold_today,
        "top_moving_products": top_moving_products,
        "total_inventory_value": total_inventory_value,
        "stock_turnover_rate": stock_turnover_rate,
        "daily_customers": daily_customers,
        "current_store": get_default_store(),
        "recent_activities": get_recent_activities(),
        "my_transfer_requests": my_transfer_requests,
    }
    metrics["critical_alerts"] = build_critical_alerts(metrics)
    return metrics


def build_critical_alerts(metrics):
    """Alerts the stores dashboard raises, built from the real metrics."""
    from django.urls import NoReverseMatch, reverse

    def _url(name):
        try:
            return reverse(name)
        except NoReverseMatch:
            return ""

    alerts = []

    if metrics["low_stock_count"]:
        alerts.append(
            {
                "type": "warning",
                "icon": "alert-triangle",
                "title": "Low stock",
                "message": (
                    f"{metrics['low_stock_count']} product line"
                    f"{'s are' if metrics['low_stock_count'] != 1 else ' is'} "
                    "at or below the reorder level."
                ),
                "action_url": _url("products_page"),
            }
        )

    if metrics["pending_transfers"] or metrics["pending_transfer_requests"]:
        parts = []
        if metrics["pending_transfers"]:
            parts.append(f"{metrics['pending_transfers']} stock transfer(s)")
        if metrics["pending_transfer_requests"]:
            parts.append(
                f"{metrics['pending_transfer_requests']} transfer request(s)"
            )
        alerts.append(
            {
                "type": "info",
                "icon": "truck-delivery",
                "title": "Transfers awaiting action",
                "message": f"{' and '.join(parts)} still need approval.",
                "action_url": _url("stock_transfer_list"),
            }
        )

    if metrics["stock_sold_today"] == 0 and metrics["stock_received_today"] == 0:
        alerts.append(
            {
                "type": "danger",
                "icon": "alert-circle",
                "title": "No stock movement today",
                "message": "Nothing has been received or sold in this store today.",
                "action_url": "",
            }
        )

    return alerts


# ---------------------------------------------------------------------------
# Charts & month-over-month deltas
# ---------------------------------------------------------------------------

def get_sales_vs_purchases_series(days=30, today=None):
    """Daily sales and purchases for the last ``days`` days."""
    today = today or date.today()
    start = today - timedelta(days=days - 1)

    sales_rows = {
        row["sale_date"]: row["total"]
        for row in Sales.objects.filter(
            sale_date__gte=start, sale_date__lte=today, is_cancelled=False
        )
        .values("sale_date")
        .annotate(total=Sum("total_amount"))
    }
    purchase_rows = {
        row["purchase_date"]: row["total"]
        for row in PurchaseOrder.objects.filter(
            purchase_date__gte=start, purchase_date__lte=today
        )
        .values("purchase_date")
        .annotate(total=Sum("total_cost"))
    }

    labels, sales, purchases = [], [], []
    for offset in range(days):
        day = start + timedelta(days=offset)
        labels.append(day.strftime("%d %b"))
        sales.append(_num(sales_rows.get(day, 0)))
        purchases.append(_num(purchase_rows.get(day, 0)))

    return {"labels": labels, "sales": sales, "purchases": purchases}


def get_revenue_vs_expenses_series(months=12, today=None):
    """Monthly revenue and expenses for the last ``months`` months."""
    today = today or date.today()
    labels, revenue, expenses = [], [], []

    for offset in range(months - 1, -1, -1):
        year = today.year
        month = today.month - offset
        while month <= 0:
            month += 12
            year -= 1
        first = date(year, month, 1)
        last = _month_bounds(first)[1]

        sales_total = Sales.objects.filter(
            sale_date__gte=first, sale_date__lte=last, is_cancelled=False
        ).aggregate(t=Sum("total_amount"))["t"] or 0
        expense_total = Expense.objects.filter(
            date__gte=first, date__lte=last
        ).aggregate(t=Sum("amount"))["t"] or 0

        labels.append(first.strftime("%b"))
        revenue.append(_num(sales_total))
        expenses.append(_num(expense_total))

    return {"labels": labels, "revenue": revenue, "expenses": expenses}


def get_customer_split(today=None):
    """Revenue from first-time customers versus returning customers.

    A customer's *first* sale is the one that makes them a first-time
    customer; every later sale counts as a return.
    """
    today = today or date.today()
    sales = (
        Sales.objects.filter(is_cancelled=False, customer__isnull=False)
        .select_related("customer")
        .order_by("customer_id", "sale_date", "id")
    )

    first_time = 0
    returning = 0
    seen = set()
    for sale in sales:
        if sale.customer_id not in seen:
            seen.add(sale.customer_id)
            first_time += _num(sale.total_amount)
        else:
            returning += _num(sale.total_amount)

    return {
        "labels": ["First Time", "Return"],
        "data": [round(first_time, 2), round(returning, 2)],
    }


def get_month_over_month(today=None):
    """This month versus last month, for the headline cards."""
    today = today or date.today()
    month_start, month_end = _month_bounds(today)
    last_month_end = month_start - timedelta(days=1)
    last_month_start = _month_bounds(last_month_end)[0]

    def _window(first, last):
        sales = Sales.objects.filter(
            sale_date__gte=first, sale_date__lte=last, is_cancelled=False
        ).aggregate(t=Sum("total_amount"))["t"] or 0
        expenses = Expense.objects.filter(date__gte=first, date__lte=last).aggregate(
            t=Sum("amount")
        )["t"] or 0
        purchases = PurchaseOrder.objects.filter(
            purchase_date__gte=first, purchase_date__lte=last
        ).aggregate(t=Sum("total_cost"))["t"] or 0
        return _num(sales), _num(expenses), _num(purchases)

    sales, expenses, purchases = _window(month_start, month_end)
    prev_sales, prev_expenses, prev_purchases = _window(last_month_start, last_month_end)

    returns = Sales.objects.filter(returns__isnull=False).aggregate(
        t=Sum("returns__amount")
    )["t"] or 0

    return {
        "sales": sales,
        "expenses": expenses,
        "purchases": purchases,
        "profit": sales - expenses,
        "prev_sales": prev_sales,
        "prev_expenses": prev_expenses,
        "prev_purchases": prev_purchases,
        "prev_profit": prev_sales - prev_expenses,
        "sales_change_pct": _change_pct(sales, prev_sales),
        "expenses_change_pct": _change_pct(expenses, prev_expenses),
        "purchases_change_pct": _change_pct(purchases, prev_purchases),
        "profit_change_pct": _change_pct(sales - expenses, prev_sales - prev_expenses),
        "returns_total": _num(returns),
    }
