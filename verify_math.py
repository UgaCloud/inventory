# math check: manage.py shell -c "exec(open('verify_math.py', encoding='utf-8').read())"
from django.db.models import Sum

from app.models.transactions import (Sales, SalesItem, PurchaseOrder, Inventory,
                                     InventoryBatch, StockAdjustment, StockAdjustmentItem)
from app.models.finance import CashFlow, DailyCashSummary
from app.models.expense import Expense
from app.models.customers import Customer
from app.models.products import Product, StoreLocation
from app.models.sales_return import SalesReturn
from app.models.transactions import StockMovement

issues = []

# ---------- 1. Sale header vs lines ----------
for s in Sales.objects.all():
    if s.total_amount != s.amount_paid + s.balance:
        issues.append(f'Sale #{s.pk} ({s.receipt_no}): total_amount {s.total_amount} != paid {s.amount_paid} + balance {s.balance}')
    items_total = sum(i.quantity * i.sale_price for i in s.items.all())
    if s.items.exists() and s.total_amount != items_total:
        issues.append(f'Sale #{s.pk}: total_amount {s.total_amount} != sum(items) {items_total}')

# ---------- 2. Perfume sales ----------
try:
    from app.models.perfume import PerfumeSaleLine
    for line in PerfumeSaleLine.objects.select_related('sale'):
        if int(line.selling_price) != int(line.sale.total_amount):
            issues.append(f'PerfumeLine #{line.pk}: selling_price {line.selling_price} != sale total {line.sale.total_amount}')
except Exception as e:
    issues.append(f'perfume check error: {e}')

# ---------- 3. Inventory vs batches ----------
bad = 0
for inv in Inventory.objects.all():
    batch_sum = InventoryBatch.objects.filter(product=inv.product, store=inv.store).aggregate(t=Sum('remaining_quantity'))['t'] or 0
    if inv.quantity_in_stock != batch_sum:
        bad += 1
        issues.append(f'Inventory({inv.product_id},{inv.store_id}): stock {inv.quantity_in_stock} != batch sum {batch_sum}')
if bad == 0:
    print(f'OK inventory==batches for {Inventory.objects.count()} rows')

# ---------- 4. Inventory vs movements (signed quantities) ----------
for inv in Inventory.objects.all():
    net = StockMovement.objects.filter(
        product=inv.product, store=inv.store
    ).aggregate(t=Sum('quantity'))['t'] or 0
    if net != inv.quantity_in_stock:
        issues.append(f'Inventory({inv.product_id},{inv.store_id}): stock {inv.quantity_in_stock} != movement net {net}')

# ---------- 5. DailyCashSummary chain & reconciliation ----------
for store in DailyCashSummary.objects.values_list('store_id', flat=True).distinct():
    prev = None
    for d in DailyCashSummary.objects.filter(store_id=store).order_by('date'):
        flow = CashFlow.objects.filter(store_id=store, date=d.date).aggregate(t=Sum('amount'))['t'] or 0
        expected_closing = d.opening_balance + flow
        if d.closing_balance != expected_closing:
            issues.append(f'DCS store{store} {d.date}: closing {d.closing_balance} != opening+flows {expected_closing} (flow={flow})')
        if prev is not None and d.opening_balance != prev.closing_balance:
            issues.append(f'DCS store{store} {d.date}: opening {d.opening_balance} != prev closing {prev.closing_balance}')
        prev = d

# ---------- 6. Expense -> CashFlow ----------
exp_ids = set(Expense.objects.values_list('id', flat=True))
cf_refs = set(CashFlow.objects.filter(transaction_type='expense').exclude(reference__isnull=True).values_list('reference', flat=True))
exp_total = Expense.objects.aggregate(t=Sum('amount'))['t'] or 0
exp_cf_total = CashFlow.objects.filter(transaction_type='EXPENSE').aggregate(t=Sum('amount'))['t'] or 0
if exp_total != -exp_cf_total:
    issues.append(f'Expenses total {exp_total} != -expense cashflows {-exp_cf_total}')

# ---------- 7. Customer ledger invariants ----------
# Customer.balance is ledger-derived: sum(debit) - sum(credit).
from app.models.customers import Payment, CustomerLedger
for c in Customer.objects.all():
    led = c.ledger_entries.aggregate(d=Sum('debit'), cr=Sum('credit'))
    net = (led['d'] or 0) - (led['cr'] or 0)
    if c.balance != net:
        issues.append(f'Customer {c.pk} ({c.name}): balance {c.balance} != ledger net {net}')
    sale_debits = (c.ledger_entries.filter(transaction_type='SALE').aggregate(t=Sum('debit'))['t'] or 0)
    sales_total = sum(s.total_amount for s in Sales.objects.filter(customer=c, is_cancelled=False))
    if sale_debits != sales_total:
        issues.append(f'Customer {c.pk} ({c.name}): ledger sale debits {sale_debits} != sales total {sales_total}')
    pay_credits = (c.ledger_entries.filter(transaction_type='PAYMENT').aggregate(t=Sum('credit'))['t'] or 0)
    sales_paid = sum(s.amount_paid for s in Sales.objects.filter(customer=c, is_cancelled=False))
    if pay_credits != sales_paid:
        issues.append(f'Customer {c.pk} ({c.name}): ledger payment credits {pay_credits} != sales amount_paid {sales_paid}')

# ---------- 8. Purchase orders ----------
for po in PurchaseOrder.objects.all():
    items_sum = sum(i.base_quantity * i.unit_cost for i in po.items.all())
    if po.total_cost != items_sum:
        issues.append(f'PO #{po.pk}: total_cost {po.total_cost} != items sum {items_sum}')

# ---------- 9. Sales returns ----------
for r in SalesReturn.objects.all():
    if r.amount < 0:
        issues.append(f'Return #{r.pk}: negative amount {r.amount}')

print('\n'.join(issues) if issues else 'ALL MATH INVARIANTS OK')
print(f'Total issues: {len(issues)}')
