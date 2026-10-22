# smoke test: manage.py shell -c "exec(open('smoke_test.py', encoding='utf-8').read())"
from django.test import Client
from django.urls import get_resolver, reverse, NoReverseMatch
from django.contrib.auth import get_user_model
import traceback

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first() or User.objects.order_by('id').first()

from app.models.transactions import (Sales, SalesItem, PurchaseOrder, PurchaseOrderItem,
                                     StockAdjustment, StockAdjustmentItem, TransferRequest,
                                     StockTransfer, Inventory)
from app.models.organization import Branch
from app.models.products import Product, Category, UnitOfMeasure, StoreLocation, Automotive, ProductUnitPrice
from app.models.products import ProductUnitPrice
from app.models.suppliers import Supplier
from app.models.customers import Customer, CustomerLedger
from app.models.human_resource import Department, Designation, Employee, Role
from app.models.notification import Notification
# Automotive comes from products module

samples = {}
def put(key, model):
    obj = model.objects.order_by('id').first()
    if obj:
        samples[key] = obj.pk

put('pk', Sales); put('product_id', Product); put('_product_id', Product)
put('store_id', StoreLocation); put('order_id', PurchaseOrder); put('item_id', PurchaseOrderItem)
put('request_id', TransferRequest); put('transfer_id', StockTransfer)
put('adjustment_id', StockAdjustment); put('automotive_id', Automotive)
put('branch_id', Branch); put('category_id', Category); put('supplier_id', Supplier)
put('pup_id', ProductUnitPrice); put('unit_id', UnitOfMeasure)
put('notification_id', Notification); put('role_id', Role); put('user_id', User)
put('employee_id', Employee); put('department_id', Department)
put('designation_id', Designation); put('ledger_id', CustomerLedger)
from app.models.finance import BankAccount, BankTransaction
from app.models.expense import Expense
from app.models.sales_return import SalesReturn
from app.models.audit import AuditLog
put('bankaccount', BankAccount); put('banktransaction', BankTransaction)
put('expense', Expense); put('return', SalesReturn)
put('customer', Customer)
put('auditlog', AuditLog)
from app.models.expense import ExpenseCategory as _EC
put('expensecategory', _EC)
_prod_with_barcode = Product.objects.exclude(barcode__isnull=True).exclude(barcode='').order_by('id').first()
samples['barcode'] = _prod_with_barcode.barcode if _prod_with_barcode else 'NONE'
from app.models.transactions import StockAdjustment as _SA
_ref = _SA.objects.exclude(reference__isnull=True).exclude(reference='').order_by('id').first()
samples['batch_reference'] = _ref.reference if _ref else 'NONE'
_inv = Inventory.objects.exclude(quantity_in_stock=0).order_by('id').first()
if _inv:
    samples['product_id2'] = _inv.product_id
    samples['store_id'] = _inv.store_id

# str kwargs
samples['report_type'] = 'all'
samples['period'] = 'monthly'
samples['format'] = 'csv'
samples['quantity'] = '5'

import re as _re
GET_PARAMS = {
    'perfume_stock_info': {'product_id': samples.get('product_id', 1), 'store_id': samples.get('store_id', 1)},
    'get_product_stock_transfer_info': {'product_id': samples.get('product_id', 1), 'store_id': samples.get('store_id', 1)},
    'product_by_barcode': {'barcode': samples.get('barcode', 'NONE')},
    'calculate_conversion': {},
    'calculate_conversion_decimal': {},
}

# Endpoints that are POST-only by design (GET 405 is correct)
POST_ONLY = {
    'api_stock_transfer_complete', 'api_stock_transfer_create', 'api_stock_transfer_start',
    'api_transfer_request_create', 'close_day', 'create_customer_ajax',
    'create_transfer_from_request', 'create_transfer_request', 'extend_session',
    'record_perfume_sale', 'update_transfer_request', 'update_transfer_status',
    'adjust_stock', 'audit_log_purge',
}

# Per-URL pk resolution: many URLs share the 'pk' / 'product_id' placeholder names
import collections
PK_SOURCE = {
    'audit_log_detail': 'auditlog',
    'sales': 'sales', 'cancel_sale': 'sales', 'sales_update_view': 'sales',
    'sales_detail': 'sales', 'sales_delete_view': 'sales',
    'sales_return_detail': 'return',
    'customer': 'customer', 'customer_detail': 'customer',
    'customer_update': 'customer', 'customer_delete': 'customer',
    'customer_add_payment': 'customer',
    'expensecategory': 'expensecategory',
    'expense_c': 'expensecategory',
    'bankaccount': 'bankaccount',
    'banktransaction': 'banktransaction',
    'expense': 'expense',
}

# URLs whose placeholder is a slug, not a numeric id.
SLUG_PLACEHOLDERS = {
    'settings_tab': 'profile',
}

def pk_for_url(name, param):
    if name.startswith('calculate_conversion') and param == 'unit_id':
        return samples.get('pup_id', 1)
    if name == 'store_inventory_batch_api' and _inv:
        return _inv.product_id if param == 'product_id' else _inv.store_id
    if name in SLUG_PLACEHOLDERS and param == 'slug':
        return SLUG_PLACEHOLDERS[name]
    if param == 'pk':
        for prefix, key in PK_SOURCE.items():
            if prefix in name and key in samples:
                return samples[key]
        return samples.get('pk', 1)
    if param == 'product_id':
        # batches-api path wants a product that has inventory
        return samples.get('product_id2', samples.get('product_id', 1))
    return samples.get(param, 1)

resolver = get_resolver()
names = sorted(set(n for n in resolver.reverse_dict.keys() if isinstance(n, str)))

def placeholders_for(name):
    """Return kwargs names needed to reverse `name`, or None if unfillable."""
    for entry in resolver.reverse_dict.getlist(name):
        pattern = entry[1]
        text = str(pattern)
        found = _re.findall(r'<(?:[^:>]*:)?([^>]+)>', text)
        kw = {}
        for p in found:
            kw[p] = pk_for_url(name, p)
        return kw
    return None

SKIP_SUBSTR = ('delete', 'approve', 'apply', 'cancel', 'mark', 'unassign', 'assign',
               'start_', 'complete_', 'bulk', 'logout', 'update_settings')
SKIP_EXACT = {'logout', 'sales_delete_view', 'delete_product', 'delete_category'}

from django.conf import settings as _settings
_settings.ALLOWED_HOSTS = list(_settings.ALLOWED_HOSTS) + ['testserver', 'localhost', '127.0.0.1']

c = Client()
c.force_login(admin)

results = {'ok': 0, 'fail': []}
for name in names:
    if any(s in name for s in SKIP_SUBSTR) or name in SKIP_EXACT or name in POST_ONLY:
        continue
    try:
        kw = placeholders_for(name)
        if kw is None:
            continue
        url = reverse(name, kwargs=kw)
    except NoReverseMatch:
        continue
    except Exception:
        results['fail'].append((name, 'REVERSE-ERR', traceback.format_exc()[-400:]))
        continue
    try:
        r = c.get(url, GET_PARAMS.get(name, {}), follow=False)
        if r.status_code >= 400:
            body = ''
            try:
                body = r.content.decode('utf-8', 'ignore')
            except Exception:
                body = ''
            if 'Error generating PDF' in body or 'Traceback' in body:
                err = body[-800:]
            else:
                err = f'HTTP {r.status_code}'
            results['fail'].append((name, url, err))
        else:
            results['ok'] += 1
    except Exception:
        results['fail'].append((name, url, traceback.format_exc()[-600:]))

print(f"OK: {results['ok']}  FAIL: {len(results['fail'])}")
for name, url, err in results['fail']:
    print('=' * 70)
    print(f'{name} -> {url}')
    print(err)
