from app.views.reports.customer_report_views import customer_balance_report
    
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from api import views

from .views.product_views import * 
from .views.accounts_views import manage_accounts_view
from .views.general_views import *
from .views.supplier_views import *
from .views.customer_view import *
from .views.transactions_views import purchase_order_view, sales_view, stock_transfer_view
from .views.organization_views import *
from .views.stock_views import *
from .views.transfer_views import *
from .views.transfers import *
from .views.sales_views import *
from .views.sales_returns_views import sales_returns_list_view, sales_return_detail_view
    
from .views.human_resource_views import *
from app.views.product_autocomplete import product_autocomplete
from app.views.expense_views import *
from app.views.expenses_report_view import expenses_report
from app.views.sales_returns_report_view import sales_returns_report
from app.views.notification_views import (
    notifications_list_view, notifications_api,
    notification_mark_read, notification_mark_all_read,
)
from app.views.automotive_views import (
    automotive_list_view, automotive_create_view,
    automotive_edit_view, automotive_delete_view,
)
from app.views.stock_intake_report_view import stock_intake_report
from app.views.global_search_view import global_search_api
from app.views.finance_views import *
from app.views.product_views import bulk_add_categories_view, download_category_template_view
from .views.reports import sales_report_views, inventory_reports
from app.views import stock_adjustments
from .views.roles_views import *
from .views.user_views import *
from .views.employee_role_views import employee_manage_roles_view
from app.views.dashboard_api import order_stats_api, recent_sales_api
from app.views import profile_views


urlpatterns = [
    path('accounts/', include('django.contrib.auth.urls')),
    path('', index_view, name = 'index_page'),
    path('login/', login_view, name = 'login_page'),
    path('reset-password/', reset_password_view, name='reset_password'),
    path('sign_up/', sign_up_view, name = 'sign_up_page'),
    path('extend-session/', extend_session_view, name = 'extend_session'),
    path('logout/', logout_view, name = 'logout'),
    path('accounts/', manage_accounts_view, name='accounts_page'),
    path('under_maintenance/', under_maintenance_view, name='under_maintenance_page'),
    
   
    path('app/dashboard/orders-by-date/', orders_by_date, name='orders_by_date_api'),
    path('expenses-report/', expenses_report, name='expenses_report'),
    path('sales-returns-report/', sales_returns_report, name='sales_returns_report'),
    path('stock-intake-report/', stock_intake_report, name='stock_intake_report'),
    path('api/global-search/', global_search_api, name='global_search_api'),

    # Notifications
    path('notifications/', notifications_list_view, name='notifications_list'),
    path('notifications/api/', notifications_api, name='notifications_api'),
    path('notifications/<int:notification_id>/mark-read/', notification_mark_read, name='notification_mark_read'),
    path('notifications/mark-all-read/', notification_mark_all_read, name='notification_mark_all_read'),

    # Automotive Management
    path('automotives/', automotive_list_view, name='automotive_list'),
    path('automotives/create/', automotive_create_view, name='automotive_create'),
    path('automotives/<int:automotive_id>/edit/', automotive_edit_view, name='automotive_edit'),
    path('automotives/<int:automotive_id>/delete/', automotive_delete_view, name='automotive_delete'),
    
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
    path('delete_product/<int:product_id>/', delete_product_view, name = 'delete_product'),
    path('product_details/<int:_product_id>/', product_details_view, name = 'product_details_page'),
    path('add_product_unit_price/', add_product_unit_price_view, name = 'add_product_unit_price_page'),
    path('edit_product_unit_price/<int:pup_id>/', update_product_unit_price_view, name = 'edit_product_unit_price_page'),
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
    path('api/purchase-order/<int:order_id>/', get_purchase_order_api, name='purchase_order_api'),
    
    # Purchase Order Items
    path('purchase_order/<int:order_id>/items/', purchase_order_item_list, name='purchase_order_item_list'),
    path('purchase_order/<int:order_id>/items/create/', create_purchase_order_item, name='create_purchase_order_item'),
    path('purchase_order/item/<int:item_id>/edit/', edit_purchase_order_item, name='edit_purchase_order_item'),
    path('purchase_order/item/<int:item_id>/delete/', delete_purchase_order_item, name='delete_purchase_order_item'),
    # Bulk upload / template for PurchaseOrderItem
    # path('purchase_order/<int:order_id>/items/bulk-upload/', purchase_order_items_bulk_upload, name='purchase_order_items_bulk_upload'),
    # path('purchase_order/items/bulk-template/', download_purchase_order_item_template, name='download_purchase_order_item_template'),
    
    # -------------------------------------------------------------------
    # TRANSFER REQUEST URLs
    # -------------------------------------------------------------------
    path('transfer_requests/', transfer_request_list, name='transfer_request_list'),
    path('transfer_requests/create/', create_transfer_request, name='create_transfer_request'),
    path('transfer_requests/<int:request_id>/', transfer_request_detail, name='transfer_request_detail'),
    path('transfer_requests/<int:request_id>/json/', transfer_request_json, name='transfer_request_json'),
    path('transfer_requests/<int:request_id>/edit/', edit_transfer_request, name='edit_transfer_request'),
    path('transfer_requests/<int:request_id>/update/', update_transfer_request, name='update_transfer_request'),
    path('transfer_requests/<int:request_id>/approve/', approve_transfer_request, name='approve_transfer_request'),
    # path('transfer_requests/<int:request_id>/approve-and-create/', approve_and_create_transfer, name='approve_and_create_transfer'),
    path('transfer_requests/<int:request_id>/print/', print_transfer_request, name='print_transfer_request'),
    path('transfer_requests/<int:request_id>/conversion-debug/', conversion_factor_debug, name='conversion_factor_debug'),
    path('transfer_requests/statuses/', transfer_request_statuses, name='transfer_request_statuses'),
    path('transfer_request_for_approval/', pending_transfer_requests_for_approval, name='transfer_request_for_approval'),
    
    # -------------------------------------------------------------------
    # STOCK TRANSFER URLs
    # -------------------------------------------------------------------
    path('stock_transfers/', stock_transfer_list, name='stock_transfer_list'),
    path('stock_transfers/create/', stock_transfer_create, name='stock_transfer_create'),
    path('stock_transfers/create/from-request/<int:request_id>/', create_transfer_from_request, name='create_transfer_from_request'),
    path('stock_transfers/direct/create/', direct_stock_transfer_create, name='direct_stock_transfer_create'),
    path('stock_transfers/bulk/create/', create_bulk_transfers, name='create_bulk_transfers'),
    path('stock_transfers/<int:transfer_id>/', stock_transfer_detail, name='stock_transfer_detail'),
    path('stock_transfers/<int:transfer_id>/update/', stock_transfer_update, name='stock_transfer_update'),
    path('stock_transfers/<int:transfer_id>/start/', start_stock_transfer, name='start_stock_transfer'),
    path('stock_transfers/<int:transfer_id>/complete/', complete_stock_transfer, name='complete_stock_transfer'),
    path('stock_transfers/<int:transfer_id>/update_status/', update_transfer_status, name='update_transfer_status'),
    
    # -------------------------------------------------------------------
    # CONVERSION FACTOR URLs
    # -------------------------------------------------------------------
    path('conversion/help/', conversion_help, name='conversion_help'),
    path('conversion/calculator/', conversion_calculator, name='conversion_calculator'),
    
    # -------------------------------------------------------------------
    # API ENDPOINTS
    # -------------------------------------------------------------------
    # Transfer Request APIs
    path('api/approved_transfer_requests/', approved_transfer_requests_api, name='approved_transfer_requests'),
    path('api/approved-transfer-requests/', approved_transfer_requests_json, name='approved_transfer_requests_json'),
    path('api/product-stock-transfer-info/', get_product_stock_transfer_info, name='get_product_stock_transfer_info'),
    
    # Product & Conversion APIs
    path('api/product/<int:product_id>/units/', get_product_units, name='product_units'),
    path('api/product/<int:product_id>/store/<int:store_id>/stock/', get_product_stock_for_store, name='product_stock_for_store'),
    path('api/conversion/calculate/<int:product_id>/<int:unit_id>/<int:quantity>/', calculate_conversion, name='calculate_conversion'),
    path('api/conversion/calculate/<int:product_id>/<int:unit_id>/<path:quantity>/', calculate_conversion, name='calculate_conversion_decimal'),

        

    # Stock Adjustments
    path('stock_adjustments/', stock_adjustment_list, name='stock_adjustment_list'),
    path('stock_adjustments/<int:adjustment_id>/', stock_adjustment_detail, name='stock_adjustment_detail'),
    path('stock_adjustments/create/', create_stock_adjustment, name='create_stock_adjustment'),
    path('stock_adjustments/<int:adjustment_id>/edit/', edit_stock_adjustment, name='edit_stock_adjustment'),
    path('stock_adjustments/<int:adjustment_id>/apply/', apply_stock_adjustment, name='apply_stock_adjustment'),
    path('stock_adjustments/<int:adjustment_id>/delete/', delete_stock_adjustment, name='delete_stock_adjustment'),

    # sales
    path('sales/', sales_list_view, name='sales_list'),
    path('sales/<int:pk>/update/', sales_update_view, name='sales_update_view'),
    path('sales/<int:pk>/detail/', sales_detail_view, name='sales_detail'),
    path('sales/<int:pk>/delete/', sales_delete_view, name='sales_delete_view'),
    path('sales/record_sale/', record_sales_view, name='record_sale'),  
    path('product-autocomplete/', product_autocomplete, name='product_autocomplete'),
    path('product_autocomplete/', product_autocomplete, name='product_autocomplete'),
    path('sales/<int:pk>/cancel/', cancel_sale_view, name='cancel_sale'),

    # Sales Returns
    path('sales/returns/', sales_returns_list_view, name='sales_returns_list'),
    path('sales/returns/<int:pk>/', sales_return_detail_view, name='sales_return_detail'),

    # API endpoints
    path('api/products/autocomplete/', product_autocomplete, name='product_autocomplete'),
    path('api/products/<int:product_id>/stock-info/', get_product_stock_info, name='product_stock_info'),
    path('api/sales/product-by-barcode/', get_product_by_barcode, name='product_by_barcode'),
    path('api/products/list/', get_products_list, name='get_products_list'),
    path('api/units/list/', get_units_list, name='get_units_list'),
    path('api/sales/validate-stock/', validate_sale_stock, name='validate_sale_stock'),
    path('api/products/<int:product_id>/details/', get_product_details, name='get_product_details'),    
    path('api/products/<int:product_id>/units/', get_product_units_json, name='get_product_units'),


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
    path('customers/create-ajax/', create_customer_ajax, name='create_customer_ajax'),
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
    path('products/<int:product_id>/unit-prices/', product_unit_prices_api, name='product_unit_prices_api'),

    # Store Inventory URLs - Complete Section
    path('stores/<int:store_id>/inventory/', store_inventory_view, name='store_inventory'),
    path('stores/<int:store_id>/inventory/export/', store_inventory_export_view, name='store_inventory_export'),
    path('stores/<int:store_id>/low-stock-api/', store_low_stock_api, name='store_low_stock_api'),
    path('stores/inventory/overview/', all_stores_inventory_view, name='all_stores_inventory'),
    path('stores/<int:store_id>/products/<int:product_id>/detail/', product_inventory_detail_view, name='product_inventory_detail'),
    path('stores/<int:store_id>/aging-report/', store_inventory_aging_report_view, name='store_inventory_aging'),
    path('stores/<int:store_id>/products/<int:product_id>/batches-api/', store_inventory_batch_api, name='store_inventory_batch_api'),

    # Product API endpoints
    path('api/products/', products_api, name='products_api'),
    path('api/products/search/', products_search_api, name='products_search_api'),
    path('api/products/<int:product_id>/stock/', product_stock_api, name='product_stock_api'),
    path('api/products/category/<int:category_id>/', products_by_category_api, name='products_by_category_api'),
    path('api/products/suggestions/', product_suggestions_api, name='product_suggestions_api'),



    
    # Sales Report URLs
    path('reports/branch-sales/', sales_report_views.branch_sales_report, name='branch_sales_report'),
    path('reports/branch-sales/api/', sales_report_views.branch_sales_report_api, name='branch_sales_report_api'),
    path('reports/branch-sales/export/csv/', sales_report_views.export_branch_sales_csv, name='export_branch_sales_csv'),
    path('reports/branch-sales/export/pdf/', sales_report_views.export_branch_sales_pdf, name='export_branch_sales_pdf'),
    path('reports/branch-comparison/', sales_report_views.branch_comparison_report, name='branch_comparison_report'),
    path('reports/sales-item-unit/', sales_report_views.sales_item_unit_report, name='sales_item_unit_report'),
    path('reports/sales-item-unit/export/csv/', sales_report_views.export_sales_item_unit_csv, name='export_sales_item_unit_csv'),
    path('reports/sales-item-unit/export/pdf/', sales_report_views.export_sales_item_unit_pdf, name='export_sales_item_unit_pdf'),
    path('adjust-stock/', stock_adjustments.adjust_stock_view, name='adjust_stock'),
    path('api/inventory/available/', stock_adjustments.api_inventory_available, name='api_inventory_available'),
    
    
    
    # Inventory Reports
    path('reports/', inventory_reports.reports_dashboard, name='reports_dashboard'),   
    path('reports-details/', inventory_reports.reports_details, name='reports_details'),
    path('reports/customer-balance/', customer_balance_report, name='customer_balance_report'),
    path('purchase-details/', inventory_reports.purchase_details, name='purchase_details'), 
    # path('sales-details/', inventory_reports.sales_details, name='sales_details'),
    path('inventory-details/', inventory_reports.inventory_details, name='inventory_details'),
    path('transfer-details/', inventory_reports.transfer_details, name='transfer_details'),
    path('stock-adjustment-details/', inventory_reports.stockadj_details, name='stock_adjustment_details'),
    path('finance/reports/', inventory_reports.financial_details, name='financial_details'),
    path('productmaster-details/', inventory_reports.productmaster_details, name='productmaster_details'),
    path('stocklocation-details/', inventory_reports.stocklocation_details, name='stocklocation_details'),
    path('reorder-details/', inventory_reports.reorder_details, name='reorder_details'), 
    path('productpricing-details/', inventory_reports.productpricing_details, name='productpricing_details'),
    path('profile-details/', profile_views.profile_view, name='profile_details'),
    
    path('inventory-details/export/pdf/', inventory_reports.export_inventory_pdf, name='export_inventory_pdf'),
   
   
     # Sales details report
    path('sales-details/', inventory_reports.sales_details, name='sales_details'),
    path('sales-details/export/csv/', inventory_reports.export_sales_csv, name='export_sales_csv'),
    path('sales-details/export/pdf/', inventory_reports.export_sales_pdf, name='export_sales_pdf'),
    path('sales-details/export/excel/', inventory_reports.export_sales_excel, name='export_sales_excel'),
   
   
    path('reports/purchase/export/csv/', inventory_reports.export_purchase_csv, name='export_purchase_csv'),
    path('reports/purchase/export/pdf/', inventory_reports.export_purchase_pdf, name='export_purchase_pdf'),
    path('reports/purchase/export/excel/', inventory_reports.export_purchase_excel, name='export_purchase_excel'),
    path('reports/purchase/<str:report_type>/', inventory_reports.purchase_details, name='purchase_report_type'),
    path('reports/purchase/<str:report_type>/<str:period>/',inventory_reports.purchase_details, name='purchase_report_period'),

    path('stock-adjustment-details/export/pdf/', inventory_reports.export_stockadj_pdf, name='export_stockadj_pdf'),
    path('transfer-details/export/pdf/', inventory_reports.export_transfer_pdf, name='export_transfer_pdf'),
    path('productmaster-details/export/pdf/', inventory_reports.export_productmaster_pdf, name='export_productmaster_pdf'),
    path('stocklocation-details/export/pdf/', inventory_reports.export_stocklocation_pdf, name='export_stocklocation_pdf'),
    path('reorder-details/export/pdf/', inventory_reports.export_reorder_pdf, name='export_reorder_pdf'),



    path('api/adjustments/<int:adjustment_id>/details/', inventory_reports.adjustment_details_api, name='adjustment_details_api'),
    path('api/adjustments/batch/<str:batch_reference>/', inventory_reports.batch_details_api, name='batch_details_api'),
  
     
    # Add these new endpoints
    path('productmaster-export/<str:format>/', inventory_reports.export_product_report, name='productmaster_export'),
    path('product-catalog-data/', inventory_reports.get_product_catalog_data, name='product_catalog_data'),
    path('product-statistics/', inventory_reports.get_product_statistics, name='product_statistics'),

  
    
    # Role Management URLs (RBAC 2.0)
    path('roles/', roles_list_view, name='roles_list_page'),
    path('roles/create/', role_create_view, name='role_create_page'),
    path('roles/<int:role_id>/', role_detail_view, name='role_detail_page'),
    path('roles/<int:role_id>/edit/', role_edit_view, name='role_edit_page'),
    path('roles/<int:role_id>/delete/', role_delete_view, name='role_delete_page'),
    path('roles/<int:role_id>/assign/<int:user_id>/', role_assign_to_user_view, name='role_assign_to_user_page'),
    path('roles/<int:role_id>/unassign/<int:user_id>/', role_unassign_from_user_view, name='role_unassign_from_user_page'),
    path('roles/<int:role_id>/bulk-assign/', role_bulk_assign_view, name='role_bulk_assign_page'),
    
    # User Management URLs (RBAC 2.0)
    path('users/', users_list_view, name='users_list_page'),
    path('users/create/', user_create_view, name='user_create_page'),
    path('users/<int:user_id>/', user_detail_view, name='user_detail_page'),
    path('users/<int:user_id>/edit/', user_edit_view, name='user_edit_page'),
    path('users/<int:user_id>/delete/', user_delete_view, name='user_delete_page'),
    path('users/<int:user_id>/assign-role/', user_assign_role_view, name='user_assign_role_page'),
    path('users/<int:user_id>/unassign-role/', user_unassign_role_view, name='user_unassign_role_page'),
    path('users/<int:user_id>/unassign-role/<int:role_id>/', user_unassign_role_view, name='user_unassign_role_page'),
    
    # Employee Role Management URLs (RBAC 2.0)
    path('employees/<int:employee_id>/manage-roles/', employee_manage_roles_view, name='employee_manage_roles_page'),
    path('dashboard/order-stats/', order_stats_api, name='order_stats_api'),
    path('dashboard/recent-sales/', recent_sales_api, name='recent_sales_api'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)