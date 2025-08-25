from app.models.organization import OrganizationSetting, Branch, Currency


def organization_setting(request):
    settings = OrganizationSetting.load()
    return {
        'organization': settings,
    }


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
                {'label': 'Branches', 'url_name': 'manage_branch_page', 'perm': 'app.view_branch'},
                {'label': 'Stores', 'url_name': 'store_page', 'perm': 'app.view_store'},
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
                {'label': 'Record Sale', 'url_name': 'record_sale', 'perm': 'sales.add_sale'},
                {'label': 'Sales List', 'url_name': 'sales_list', 'perm': 'sales.view_sale'},
                {'label': 'Sales Return', 'url_name': 'under_maintenance_page'},
                {'label': 'Quotation', 'url_name': 'under_maintenance_page'},
                {
                    'label': 'Customer',
                    'children': [
                        {'label': 'Manage Customers', 'url_name': 'customer_list', 'perm': 'app.view_customer'},
                        {'label': 'Payments', 'url_name': None},
                        {'label': 'Customer Ledgers', 'url_name': 'customer_ledger_list', 'perm': 'app.view_customerledger'},
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
                        {'label': 'Expenses', 'url_name': 'expense_list', 'perm': 'app.view_expense'},
                        {'label': 'Expense Category', 'url_name': 'expensecategory_list', 'perm': 'app.view_expensecategory'},
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
