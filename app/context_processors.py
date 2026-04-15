from app.models.organization import OrganizationSetting, Branch, Currency
from .models.transactions import TransferRequest
from app.forms.transaction_forms import *
from app.models.products import *
from app.models.human_resource import UserProfile
from app.utils.module_mapping import (
    user_has_module_access,
    get_module_id_for_url,
)


def organization_setting(request):
    settings = OrganizationSetting.load()
    
    user_roles = []
    user = request.user
    if user.is_authenticated:
        try:
            user_roles = list(user.profile.roles.values_list('name', flat=True))
        except UserProfile.DoesNotExist:
            user_roles = []
    
    return {
        'organization': settings,
        'is_admin': is_admin(user),
        'is_manager': is_manager(user),
        'is_accountant': is_accountant(user),
        'is_sales': is_sales(user),
        'is_stores': is_stores(user),
        'is_superuser': is_superuser(user), 
        'branches': Branch.objects.all(),
        'currencies': Currency.objects.all(),
        'user_roles': user_roles,
    }

def is_superuser(user):
    return user.is_authenticated and user.is_superuser

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name='Admin').exists())

def is_manager(user):
    return user.is_authenticated and user.groups.filter(name='Manager').exists()

def is_accountant(user):
    return user.is_authenticated and user.groups.filter(name='Accountant').exists()

def is_sales(user):
    return user.is_authenticated and user.groups.filter(name='Sales').exists()

def is_stores(user):
    return user.is_authenticated and user.groups.filter(name='Stores').exists()

# New context processor: builds a menu structure and filters it per user module access
def app_menu(request):
    user = request.user

    raw_menu = [
        {
            'label': 'Main Menu',
            'icon': 'ti ti-layout-grid fs-16 me-2',
            'children': [
                {'label': 'Dashboard', 'url_name': 'index_page'}
                # {
                #     'label': 'Dashboard',
                #     'children': [
                #         {'label': 'Dashboard', 'url_name': 'index_page'},
                #         # {'label': 'Admin Dashboard 2', 'url_name': 'index_page'},
                #         # {'label': 'Sales Dashboard', 'url_name': 'under_maintenance_page'},
                #     ],
                # }
            ],
        },
        {
            'label': 'Inventory',
            'icon': 'ti ti-brand-unity fs-16 me-2',
            'children': [
                {'label': 'Branches', 'url_name': 'manage_branch_page'},
                {'label': 'Stores', 'url_name': 'all_stores_inventory'},
                {'label': 'Category', 'url_name': 'add_category_page'},
                {'label': 'Units', 'url_name': 'unit_of_measure_page'},
                {'label': 'Products', 'url_name': 'products_page'},
            ],
        },
        {
            'label': 'Stock',
            'icon': 'ti ti-layout-grid fs-16 me-2',
            'children': [
                {'label': 'Manage Stock', 'url_name': 'purchase_order_list'},
                {'label': 'Request Stock', 'url_name': 'transfer_request_list'},
                # {'label': 'Manage Requisitions', 'url_name': 'transfer_request_for_approval'},
                {'label': 'Stock Transfer', 'url_name': 'stock_transfer_list'},
                {'label': 'Stock Adjustment', 'url_name': 'stock_adjustment_list'},
                {'label': 'Supplier', 'url_name': 'supplier_page'},
            ],
        },
        {
            'label': 'Sales',
            'icon': 'ti ti-layout-grid fs-16 me-2',
            'children': [
                {'label': 'Record Sale', 'url_name': 'record_sale'},
                {'label': 'Sales List', 'url_name': 'sales_list'},
                {'label': 'Sales Returns', 'url_name': 'sales_returns_list'},
                # {'label': 'Quotation', 'url_name': 'under_maintenance_page'},
                {
                    'label': 'Customer',
                    'children': [
                        {'label': 'Manage Customers', 'url_name': 'customer_list'},
                        # {'label': 'Payments', 'url_name': None},
                        {'label': 'Customer Ledgers', 'url_name': 'customer_ledger_list'},
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
                        {'label': 'Expenses', 'url_name': 'expense_list'},
                        {'label': 'Expense Category', 'url_name': 'expensecategory_list'},
                    ],
                },
                {'label': 'Bank Accounts', 'url_name': 'bankaccount_list'},
                {'label': 'Bank Transactions', 'url_name': 'banktransaction_list'},
                {'label': 'Cash Flow', 'url_name': 'cashflow_list'},
            ],
        },
        {
            'label': 'Staff',
            'icon': 'ti ti-page-break fs-16 me-2',
            'children': [
                {'label': 'Employees', 'url_name': 'employee_page'},
                {'label': 'Departments', 'url_name': 'department_page'},
                {'label': 'Designations', 'url_name': 'designation_page'},
            ],
        },
        {
            'label': 'User Management',
            'icon': 'ti ti-circle-plus fs-16 me-2',
            'children': [
                {'label': 'Users', 'url_name': 'users_list_page'},
                {'label': 'Roles & Permissions', 'url_name': 'roles_list_page'},
            ],
        },
       {
            'label': 'Reports',
            'icon': 'ti ti-chart-bar fs-16 me-2',
            'children': [
                
                # {'label': 'Report Dashboard', 'url_name': 'reports_dashboard'},  
                # {'label': 'Report details', 'url_name': 'reports_details'},
                {'label': 'Sales Report', 'url_name': 'sales_details'},
                {'label': 'Balance Report', 'url_name': 'customer_balance_report'},
                {'label': 'Expenses Report', 'url_name': None},
                {'label': 'Purchase Report', 'url_name': 'purchase_details'},
                {'label': 'Inventory Report', 'url_name': 'inventory_details'},
                {'label': 'Transfer Report', 'url_name': 'transfer_details'},
                {'label': 'Stock Adjustment Report', 'url_name': 'stock_adjustment_details'},
                # {'label': 'Financial Report', 'url_name': 'financial_details'},
                {'label': 'Product Master Report', 'url_name': 'productmaster_details'},
                {'label': 'Stock Location Report', 'url_name': 'stocklocation_details'},
                # {'label': 'reorder Level Report', 'url_name': 'reorder_details'},
                # {'label': 'Product Pricing Report', 'url_name': 'productpricing_details'},
                
                
                
                
                # {'label': 'Branch Sales Report', 'url_name': 'branch_sales_report'},
                # {'label': 'Sales Item Report', 'url_name': 'sales_item_unit_report'},
                
            ],
        },
        {
            'label': 'Settings',
            'icon': 'ti ti-settings fs-16 me-2',
            'children': [
                {'label': 'Company Profile', 'url_name': 'settings_page'},
            ],
        },
    ]

    def item_allowed(item):
        """Check if menu item is allowed based on module access"""
        # Superuser sees everything
        if getattr(user, 'is_superuser', False):
            return True

        if item.get('auth_required', True) and not user.is_authenticated:
            return False

        url_name = item.get('url_name')
        if url_name:
            if url_name == 'under_maintenance_page':
                return False
            module_id = get_module_id_for_url(url_name)
            if module_id is None:
                return False
            return user_has_module_access(user, module_id)

        # Items without URL are only shown if they keep permitted children
        return False

    def filter_menu(items):
        """Recursively filter menu items based on module access"""
        out = []
        for it in items:
            # Shallow copy
            new_it = it.copy()
            children = it.get('children')
            if children:
                filtered_children = filter_menu(children)
                if filtered_children:
                    new_it['children'] = filtered_children
                else:
                    new_it.pop('children', None)
            
            # Decide if this item itself is allowed
            include_self = item_allowed(it)
            if include_self or new_it.get('children'):
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


def stock_transfer_forms(request):
    """Provide stock transfer forms to templates"""
    if request.user.is_authenticated:
        return {
            'stock_form': StockTransferForm(),
            'item_formset': StockTransferItemFormSet(),
            'products': Product.objects.filter(is_active=True),
            'units': UnitOfMeasure.objects.all(),
        }
    return {}










