from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from .views.product_views import * 
from .views.accounts_views import manage_accounts_view
from .views.general_views import *
from .views.supplier_views import *
from .views.customer_view import *
from .views.transactions_views import purchase_order_view, sales_view, stock_transfer_view
from .views.organization_views import *
from .views.stock_views import *
from .views.transfer_views import *
from .views.sales_views import *
from .views.human_resource_views import *
from app.views.product_autocomplete import product_autocomplete
from app.views.expense_views import *
from app.views.finance_views import *
from app.views.product_views import bulk_add_categories_view, download_category_template_view

urlpatterns = [
    path('accounts/', include('django.contrib.auth.urls')),
    path('', index_view, name = 'index_page'),
    path('login/', login_view, name = 'login_page'),
    path('sign_up/', sign_up_view, name = 'sign_up_page'),
    path('accounts/', manage_accounts_view, name='accounts_page'),
    path('under_maintenance/', under_maintenance_view, name='under_maintenance_page'),
    
    # Organization
    path('branches/', manage_branches, name = 'manage_branch_page'),
    path('edit_branch/<int:branch_id>/', edit_branch, name = 'edit_branch_page'),
    path('delete_branch/<int:branch_id>/', delete_branch, name = 'delete_branch_page'),
    path('settings/', settings_page,name="settings_page"),
    path('update_settings/', update_organization_settings, name="update_settings_page"),

    # Product
    path('products/', manage_product_view, name ='products_page'),
    path('add_product/', add_product_view, name = 'add_products_page'),
    path('edit_product/<int:product_id>', edit_product_view, name = 'edit_product_page'),
    path('product_details/<int:_product_id>/', product_details_view, name = 'product_details_page'),
    path('add_product_unit_price/', add_product_unit_price_view, name = 'add_product_unit_price_page'),
    path('edit_unit_of_measure/<int:unit_id>', edit_unit_of_measure_view, name = 'edit_unit_of_measure_page'),
    path('edit_store/<int:store_id>/', edit_store_view, name = 'edit_store_page'),
    
    # Category
    path('add_category/', add_category_view, name = 'add_category_page'),
    path('delete_category/<int:category_id>/',delete_category_view, name = 'delete_category'),
    path('edit_category/<int:category_id>/',edit_category_view, name = 'edit_category_page'),
    
    path('unit_of_measure/', unit_of_measure_view, name = 'unit_of_measure_page'),
    path('supplier/', supplier_view, name = 'supplier_page'),
    path('edit_supplier/<int:supplier_id>', edit_supplier_view, name = 'edit_supplier_page'),
    path('inventory/', add_inventory_view, name = 'add_inventory_page'),
    path('store/', store_view, name = 'store_page'),
    path('purchase/', purchase_order_view, name = 'purchase_order_page'),
    path('stock_transfer/', stock_transfer_view, name = 'stock_transfer_page'),
    # path('delete_multiple/', DeleteMultipleSuppliers.as_view(), name = 'delete_multiple'),

    # Purchase Order
    path('purchase_orders/', purchase_order_list, name='purchase_order_list'),
    path('purchase_order/<int:order_id>/', purchase_order_detail, name='purchase_order_detail'),
    path('purchase_order/create/', create_purchase_order, name='create_purchase_order'),
    path('purchase_order/<int:order_id>/edit/', edit_purchase_order, name='edit_purchase_order'),
    path('purchase_order/<int:order_id>/delete/', delete_purchase_order, name='delete_purchase_order'),

    # Purchase Order Items
    path('purchase_order/<int:order_id>/items/', purchase_order_item_list, name='purchase_order_item_list'),
    path('purchase_order/<int:order_id>/items/create/', create_purchase_order_item, name='create_purchase_order_item'),
    path('purchase_order/item/<int:item_id>/edit/', edit_purchase_order_item, name='edit_purchase_order_item'),
    path('purchase_order/item/<int:item_id>/delete/', delete_purchase_order_item, name='delete_purchase_order_item'),
    # Bulk upload / template for PurchaseOrderItem
    path('purchase_order/<int:order_id>/items/bulk-upload/', purchase_order_items_bulk_upload, name='purchase_order_items_bulk_upload'),
    path('purchase_order/items/bulk-template/', download_purchase_order_item_template, name='download_purchase_order_item_template'),

    # Transfer Requests
    path('transfer_requests/', transfer_request_list, name='transfer_request_list'),
    path('transfer_requests/add/', add_transfer_request, name='add_transfer_request'),
    path('transfer_requests/<int:request_id>/', transfer_request_detail, name='transfer_request_detail'),
    path('transfer_requests/<int:request_id>/update/', update_transfer_request, name='update_transfer_request'),
    path('transfer_requests/<int:request_id>/approve/', approve_transfer_request, name='approve_transfer_request'),
    path('transfer_request_for_approval/', pending_transfer_requests_for_approval, name='transfer_request_for_approval'),

    # Stock Transfers
    path('stock_transfers/', stock_transfer_list, name='stock_transfer_list'),
    path('stock_transfers/<int:pk>/', stock_transfer_detail, name='stock_transfer_detail'),
    path('stock_transfers/create/', stock_transfer_create, name='stock_transfer_create'),
    path('stock_transfers/<int:pk>/update/', stock_transfer_update, name='stock_transfer_update'),

    # sales
    path('sales/', sales_list_view, name='sales_list'),
    path('sales/<int:pk>/update/', sales_update_view, name='sales_update_view'),
    path('sales/<int:pk>/detail/', sales_detail_view, name='sales_detail'),
    path('sales/<int:pk>/delete/', sales_delete_view, name='sales_delete_view'),
    path('sales/record_sale/', record_sales_view, name='record_sale'),  
    path('product-autocomplete/', product_autocomplete, name='product_autocomplete'),
    path('product_autocomplete/', product_autocomplete, name='product_autocomplete'),

    #human resource
    path('employee_profile/<int:employee_id>', employee_profile_view, name = 'employee_profile_page'),
    path('employee_profile/', employee_profile_view, name = 'employee_profile_page'),
    path('employee_grid', employee_grid_view, name = 'employee_page'),
    path('edit_employee/<int:employee_id>', edit_employee_view, name = 'edit_employee_page'),
    path('department_grid', department_grid_view, name = 'department_page'),
    path('edit_department/<int:department_id>', edit_department_view, name = 'edit_department_page'),
    path('designation', designation_view, name = 'designation_page'),
    path('edit_designation/<int:designation_id>', edit_designation_view, name = 'edit_designation_page'),

    # Expense URLs
    path('expenses/', expense_list_view, name='expense_list'),
    path('expenses/add/', add_expense_view, name='add_expense_page'),
    path('expenses/<int:pk>/', expense_detail_view, name='expense_detail_page'),
    path('expenses/<int:pk>/edit/', expense_update_view, name='edit_expense_page'),
    path('expenses/<int:pk>/delete/', delete_expense_view, name='delete_expense_page'),

    path('expensecategories/', expensecategory_list_view, name='expensecategory_list'),
    path('expensecategories/add/', add_expensecategory_view, name='add_expense_category_page'),
    path('expensecategories/<int:pk>/edit/', update_expensecategory_view, name='edit_expense_category_page'),
    path('expensecategories/<int:pk>/delete/', expensecategory_delete, name='delete_expensecategory_page'),

    # BankAccount URLs
    path('bankaccounts/', bankaccount_list_view, name='bankaccount_list'),
    path('bankaccounts/add/', add_bankaccount_view, name='add_bankaccount_page'),
    path('bankaccounts/<int:pk>/edit/', update_bankaccount_view, name='edit_bankaccount_page'),
    path('bankaccounts/<int:pk>/delete/', delete_bankaccount_view, name='delete_bankaccount_page'),

    # BankTransaction URLs
    path('banktransactions/', banktransaction_list_view, name='banktransaction_list'),
    path('banktransactions/add/', add_banktransaction_view, name='add_banktransaction_page'),
    path('banktransactions/<int:pk>/edit/', update_banktransaction_view, name='edit_banktransaction_page'),
    path('banktransactions/<int:pk>/delete/', delete_banktransaction_view, name='delete_banktransaction_page'),

    # Customer URLs
    path('customers/', customer_list_view, name='customer_list'),
    path('customers/add/', customer_create_view, name='customer_create'),
    path('customers/<int:pk>/', customer_detail_view, name='customer_detail'),
    path('customers/<int:pk>/edit/', customer_update_view, name='customer_update'),
    path('customers/<int:pk>/delete/', customer_delete_view, name='customer_delete'),
    path('customers/<int:pk>/add-payment/', record_customer_payment_view, name='customer_add_payment'),
    path('customers/ledgers/', customer_ledger_list_view, name='customer_ledger_list'),
    path('customers/ledgers/<int:ledger_id>/', customer_ledger_detail_view, name='customer_ledger_detail'),

    # CashFlow URLs
    path('cashflows/', cashflow_list_view, name='cashflow_list'),

    # Manual close day (DailyCashSummary) URL
    path('finance/close_day/', close_day_view, name='close_day'),
    path('products/categories/bulk-add/', bulk_add_categories_view, name='bulk_add_categories'),
    path('products/categories/bulk-template/', download_category_template_view, name='download_category_template'),
    path('products/bulk-add/', bulk_add_products_view, name='bulk_add_products'),
    path('products/bulk-template/', download_product_template_view, name='download_product_template'),
    # Product Unit Prices bulk upload and template
    path('products/unit-prices/bulk-add/', bulk_add_product_unit_prices_view, name='bulk_add_product_unit_prices'),
    path('products/unit-prices/bulk-template/', download_product_unit_price_template_view, name='download_product_unit_price_template'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)