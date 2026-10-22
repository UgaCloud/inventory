"""
Module mapping for navigation and permission enforcement.
Maps URL names to module IDs for access control.
"""
from app.models.human_resource import get_module_name_by_id

# Map URL names to module IDs
# This determines which module each view belongs to
MENU_MODULE_MAP = {
    # Main Menu / Dashboard - Module 1
    'index_page': 1,
    
    # Inventory - Module 2
    'manage_branch_page': 2,
    'all_stores_inventory': 2,
    'add_category_page': 2,
    'edit_category_page': 2,
    'unit_of_measure_page': 2,
    'products_page': 2,
    'add_products_page': 2,
    'edit_product_page': 2,
    'product_details_page': 2,
    'store_page': 2,
    'edit_store_page': 2,
    
    # Automotive Management - Module 2
    'automotive_list': 2,
    'automotive_create': 2,
    'automotive_edit': 2,
    'automotive_delete': 2,

    # Stock - Module 3
    'purchase_order_list': 3,
    'purchase_order_detail': 3,
    'create_purchase_order': 3,
    'edit_purchase_order': 3,
    'delete_purchase_order': 3,
    'transfer_request_list': 3,
    'create_transfer_request': 3,
    'transfer_request_detail': 3,
    'edit_transfer_request': 3,
    'approve_transfer_request': 3,
    'reject_transfer_request': 3,
    'transfer_request_for_approval': 3,
    'stock_transfer_list': 3,
    'stock_transfer_create': 3,
    'create_transfer_from_request': 3,
    'direct_stock_transfer_create': 3,
    'stock_transfer_detail': 3,
    'stock_transfer_update': 3,
    'stock_adjustment_list': 3,
    'create_stock_adjustment': 3,
    'edit_stock_adjustment': 3,
    'apply_stock_adjustment': 3,
    'delete_stock_adjustment': 3,
    'supplier_page': 3,
    'edit_supplier_view': 3,
    
    # Sales - Module 4
    'record_sale': 4,
    'sales_list': 4,
    'sales_detail': 4,
    'sales_update_view': 4,
    'sales_delete_view': 4,
    'customer_list': 4,
    'customer_create': 4,
    'customer_detail': 4,
    'customer_update': 4,
    'customer_delete': 4,
    'customer_add_payment': 4,
    'customer_ledger_list': 4,
    'customer_ledger_detail': 4,
    
    # Staff/HR - Module 5
    'employee_page': 5,
    'employee_profile_page': 5,
    'edit_employee_page': 5,
    'department_page': 5,
    'edit_department_page': 5,
    'designation_page': 5,
    'edit_designation_page': 5,
    
    # Finance - Module 6
    'expense_list': 6,
    'add_expense_page': 6,
    'expense_detail_page': 6,
    'edit_expense_page': 6,
    'delete_expense_page': 6,
    'expensecategory_list': 6,
    'add_expense_category_page': 6,
    'edit_expense_category_page': 6,
    'delete_expensecategory_page': 6,
    'bankaccount_list': 6,
    'add_bankaccount_page': 6,
    'edit_bankaccount_page': 6,
    'delete_bankaccount_view': 6,
    'banktransaction_list': 6,
    'add_banktransaction_page': 6,
    'edit_banktransaction_page': 6,
    'delete_banktransaction_view': 6,
    'cashflow_list': 6,
    'close_day': 6,
    
    # User Management - Module 7
    'users_list_page': 7,
    'user_create_page': 7,
    'user_detail_page': 7,
    'user_edit_page': 7,
    'user_delete_page': 7,
    'user_assign_role_page': 7,
    'user_unassign_role_page': 7,
    
    # Sales Returns
    'sales_returns_list': 4,
    'sales_returns_report': 8,
    
    # Reports - Module 8
    'branch_sales_report': 8,
    'expenses_report': 8,
    'sales_returns_report': 8,
    'stock_intake_report': 8,
    'branch_comparison_report': 8,
    'sales_item_unit_report': 8,
    'export_branch_sales_csv': 8,
    'export_branch_sales_pdf': 8,
    'export_sales_item_unit_csv': 8,
    'export_sales_item_unit_pdf': 8,
    
    # Settings - Module 9
    'settings_page': 9,
    'settings_tab': 9,
    'company_settings_page': 9,
    'update_settings_page': 9,
    'audit_log_page': 9,
    'audit_log_detail': 9,
    'audit_log_export': 9,
    
    # Dashboard - Module 10 (same as Main Menu, but separate for clarity)
    'index_page': 10,
    
    # Batch Management - Module 11
    # (Add specific batch management URLs when available)
    
    # Supplier Management - Module 12
    'supplier_page': 12,
    'edit_supplier_view': 12,
    
    # Customer Management - Module 13
    'customer_list': 13,
    'customer_create': 13,
    'customer_detail': 13,
    'customer_update': 13,
    'customer_delete': 13,
    'customer_add_payment': 13,
    'customer_ledger_list': 13,
    'customer_ledger_detail': 13,
    
    # Expense Management - Module 14
    'expense_list': 14,
    'add_expense_page': 14,
    'expense_detail_page': 14,
    'edit_expense_page': 14,
    'delete_expense_page': 14,
    'expensecategory_list': 14,
    'add_expense_category_page': 14,
    'edit_expense_category_page': 14,
    'delete_expensecategory_page': 14,
    
    # Role Management - Module 15
    'roles_list_page': 15,
    'role_create_page': 15,
    'role_detail_page': 15,
    'role_edit_page': 15,
    'role_delete_page': 15,
    'role_assign_to_user_page': 15,
    'role_unassign_from_user_page': 15,
    
    # Accounting - Module 16
    'bankaccount_list': 16,
    'add_bankaccount_page': 16,
    'edit_bankaccount_page': 16,
    'delete_bankaccount_view': 16,
    'banktransaction_list': 16,
    'add_banktransaction_page': 16,
    'edit_banktransaction_page': 16,
    'delete_banktransaction_view': 16,
    'cashflow_list': 16,
    'close_day': 16,
}

def get_module_id_for_url(url_name):
    """Get module ID for a given URL name"""
    return MENU_MODULE_MAP.get(url_name)

def get_module_name(module_id):
    """Get module name by ID"""
    return get_module_name_by_id(module_id)

def user_has_module_access(user, module_id):
    """Check if user has access to a specific module (RBAC 2.0: uses effective_modules)"""
    if not user.is_authenticated:
        return False
    
    # Superusers have access to everything
    if user.is_superuser:
        return True
    
    try:
        profile = user.profile
        if profile:
            # RBAC 2.0: Use effective_modules (union of all role modules)
            effective = profile.effective_modules
            return module_id in effective
    except AttributeError:
        pass
    
    return False

def user_has_url_access(user, url_name):
    """Check if user has access to a specific URL"""
    module_id = get_module_id_for_url(url_name)
    if module_id is None:
        # If URL is not in map, allow access (backward compatibility)
        return True
    return user_has_module_access(user, module_id)


# ---------------------------------------------------------------------------
# Dashboard quick actions
# ---------------------------------------------------------------------------
# Shortcuts shown on the dashboard. Each entry names the target URL and the
# module that grants access to it, so the dashboard only ever offers a
# shortcut the signed-in user can actually open.
QUICK_ACTIONS = [
    {'label': 'Record a sale', 'icon': 'ti-shopping-cart', 'url_name': 'record_sale', 'module': 4, 'tone': 'primary'},
    {'label': 'Add a customer', 'icon': 'ti-users', 'url_name': 'customer_create', 'module': 13, 'tone': 'success'},
    {'label': 'Add a product', 'icon': 'ti-package', 'url_name': 'add_products_page', 'module': 2, 'tone': 'warning'},
    {'label': 'Record an expense', 'icon': 'ti-receipt', 'url_name': 'add_expense_page', 'module': 14, 'tone': 'danger'},
    {'label': 'New purchase order', 'icon': 'ti-truck-delivery', 'url_name': 'create_purchase_order', 'module': 3, 'tone': 'primary'},
    {'label': 'Adjust stock', 'icon': 'ti-layers', 'url_name': 'create_stock_adjustment', 'module': 3, 'tone': 'secondary'},
    {'label': 'Stock transfer', 'icon': 'ti-exchange', 'url_name': 'stock_transfer_list', 'module': 3, 'tone': 'secondary'},
    {'label': 'Manage staff', 'icon': 'ti-users-group', 'url_name': 'employee_page', 'module': 5, 'tone': 'info'},
    {'label': 'Team members', 'icon': 'ti-user-cog', 'url_name': 'users_list_page', 'module': 7, 'tone': 'info'},
    {'label': 'Roles & permissions', 'icon': 'ti-shield', 'url_name': 'roles_list_page', 'module': 15, 'tone': 'warning'},
    {'label': 'Bank accounts', 'icon': 'ti-wallet', 'url_name': 'bankaccount_list', 'module': 6, 'tone': 'secondary'},
    {'label': 'Close the day', 'icon': 'ti-clock-check', 'url_name': 'close_day', 'module': 6, 'tone': 'secondary'},
    {'label': 'Company settings', 'icon': 'ti-settings', 'url_name': 'settings_page', 'module': 9, 'tone': 'secondary'},
]


def get_quick_actions(user, actions=None, limit=8):
    """The dashboard shortcuts the signed-in user is allowed to open.

    A shortcut is offered when the user has access to the module that
    guards the target page. Superusers see every shortcut. The result is
    sorted so the most frequent tasks come first, then trimmed to ``limit``.
    """
    from django.urls import NoReverseMatch, reverse

    if actions is None:
        actions = QUICK_ACTIONS

    if not user or not getattr(user, 'is_authenticated', False):
        return []

    allowed = []
    for action in actions:
        if not user_has_module_access(user, action['module']):
            continue
        try:
            url = reverse(action['url_name'])
        except NoReverseMatch:
            continue
        allowed.append({**action, 'url': url})

    return allowed[:limit]


