from app.models.organization import OrganizationSetting, Branch, Currency
from .models.transactions import TransferRequest


def organization_setting(request):
    settings = OrganizationSetting.load()
    return {
        'organization': settings,
        'is_admin': is_admin(request.user),
        'is_manager': is_manager(request.user),
        'is_accountant': is_accountant(request.user),
        'is_sales': is_sales(request.user),
        'is_stores': is_stores(request.user),
        'branches': Branch.objects.all(),
        'currencies': Currency.objects.all(),
    }

def is_superuser(user):
    return user.is_authenticated and user.is_superuser

def is_admin(user):
    return user.is_authenticated and user.groups.filter(name='Admin').exists()

def is_manager(user):
    return user.is_authenticated and user.groups.filter(name='Manager').exists()

def is_accountant(user):
    return user.is_authenticated and user.groups.filter(name='Accountant').exists()

def is_sales(user):
    return user.is_authenticated and user.groups.filter(name='Sales').exists()

def is_stores(user):
    return user.is_authenticated and user.groups.filter(name='Stores').exists()

# New context processor: builds a menu structure and filters it per user roles/permissions
def app_menu(request):
    user = request.user

    raw_menu = [
        {
            'label': 'Main Menu',
            'icon': 'ti ti-layout-grid fs-16 me-2',
            'children': [
                {
                    'label': 'Dashboard',
                    'children': [
                        {'label': 'Dashboard', 'url_name': 'index_page'},
                        {'label': 'Admin Dashboard 2', 'url_name': 'index_page'},
                        {'label': 'Sales Dashboard', 'url_name': 'under_maintenance_page'},
                    ],
                }
            ],
        },
        {
            'label': 'Inventory',
            'icon': 'ti ti-brand-unity fs-16 me-2',
            'children': [
                {'label': 'Branches', 'url_name': 'manage_branch_page', 'perm': 'app.view_branch', 'groups': ['Admin']},
                {'label': 'Stores', 'url_name': 'store_page', 'perm': 'app.view_store', 'groups': ['Admin', 'Manager']},
                {'label': 'Category', 'url_name': 'add_category_page', 'perm': 'app.view_category'},
                {'label': 'Units', 'url_name': 'unit_of_measure_page', 'perm': 'app.view_unit'},
                {'label': 'Products', 'url_name': 'products_page', 'perm': 'app.view_product'},
            ],
        },
        {
            'label': 'Stock',
            'icon': 'ti ti-layout-grid fs-16 me-2',
            'children': [
                {'label': 'Manage Stock', 'url_name': 'purchase_order_list', 'perm': 'app.view_purchaseorder'},
                {'label': 'Request Stock', 'url_name': 'transfer_request_list', 'perm': 'app.view_transferrequest'},
                {'label': 'Manage Requisitions', 'url_name': 'transfer_request_for_approval', 'perm': 'app.view_transferrequest'},
                {'label': 'Stock Transfer', 'url_name': 'stock_transfer_list', 'perm': 'app.view_stocktransfer'},
                {'label': 'Stock Adjustment', 'url_name': 'stock_adjustment_list', 'perm': 'app.view_stockadjustment'},
                {'label': 'Supplier', 'url_name': 'supplier_page', 'perm': 'app.view_supplier'},
            ],
        },
        {
            'label': 'Sales',
            'icon': 'ti ti-layout-grid fs-16 me-2',
            'children': [
                {'label': 'Record Sale', 'url_name': 'record_sale', 'perm': 'sales.add_sale', 'groups': ['Admin', 'Sales', 'Manager']},
                {'label': 'Sales List', 'url_name': 'sales_list', 'perm': 'app.view_sale', 'groups': ['Admin', 'Sales', 'Manager']},
                {'label': 'Sales Return', 'url_name': 'under_maintenance_page'},
                {'label': 'Quotation', 'url_name': 'under_maintenance_page'},
                {
                    'label': 'Customer',
                    'children': [
                        {'label': 'Manage Customers', 'url_name': 'customer_list', 'perm': 'app.view_customer', 'groups': ['Admin', 'Manager']},
                        {'label': 'Payments', 'url_name': None},
                        {'label': 'Customer Ledgers', 'url_name': 'customer_ledger_list', 'perm': 'app.view_customerledger', 'groups': ['Admin', 'Manager']},
                    ],
                },
            ],
        },
        {
            'label': 'Finance',
            'icon': 'ti ti-users-group fs-16 me-2',
            'children': [
                {
                    'label': 'Expenses',
                    'children': [
                        {'label': 'Expenses', 'url_name': 'expense_list', 'perm': 'app.view_expense', 'groups': ['Admin', 'Manager', 'Accountant']},
                        {'label': 'Expense Category', 'url_name': 'expensecategory_list', 'perm': 'app.view_expensecategory', 'groups': ['Admin', 'Manager', 'Accountant']},
                    ],
                },
                {'label': 'Bank Accounts', 'url_name': 'bankaccount_list', 'perm': 'app.view_bankaccount'},
                {'label': 'Bank Transactions', 'url_name': 'banktransaction_list', 'perm': 'app.view_banktransaction'},
                {'label': 'Cash Flow', 'url_name': 'cashflow_list', 'perm': 'app.view_cashflow'},
            ],
        },
    ]

    def item_allowed(item):
        # superuser sees everything
        if getattr(user, 'is_superuser', False):
            return True
        # if item explicitly requires login
        if item.get('auth_required', True) and not user.is_authenticated:
            return False
        # permission-based
        perm = item.get('perm')
        if perm:
            try:
                if user.has_perm(perm):
                    return True
                return False
            except Exception:
                return False
        # groups-based
        groups = item.get('groups')
        if groups:
            return user.groups.filter(name__in=groups).exists()
        # default allow
        return True

    def filter_menu(items):
        out = []
        for it in items:
            # shallow copy
            new_it = it.copy()
            children = it.get('children')
            if children:
                filtered_children = filter_menu(children)
                if filtered_children:
                    new_it['children'] = filtered_children
                else:
                    new_it.pop('children', None)
            # decide if this item itself is allowed
            if item_allowed(it) or new_it.get('children'):
                out.append(new_it)
        return out

    filtered = filter_menu(raw_menu)

    return {
        'app_menu': filtered,
    }

def transfer_notifications(request):
    """Add transfer-related notifications to template context"""
    
    if request.user.is_authenticated:
        pending_approvals = TransferRequest.objects.filter(
            status='pending'
        ).count()
        
        pending_transfers = TransferRequest.objects.filter(
            status='approved',
            stock_transfers__isnull=True
        ).count()
        
        return {
            'pending_approvals': pending_approvals,
            'pending_transfers': pending_transfers,
        }
    
    return {}
