from django.contrib import admin
from django.urls import path, include
from django.conf import settings

from .views.general_views import index_view
from .views.product_views import * 
from .views.accounts_views import manage_accounts_view
from .views.general_views import *
from .views.supplier_views import *
from .views.customer_view import customer_view
from .views.transactions_views import purchase_order_view, sales_view, stock_transfer_view
from .views.organization_views import *
from .views.stock_views import *
from .views.transfer_views import *
from .views.sales_views import *
from app.views.product_autocomplete import product_autocomplete

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

    # Product
    path('products/', manage_product_view, name ='products_page'),
    path('add_product/', add_product_view, name = 'add_products_page'),
    path('edit_product/<int:product_id>', edit_product_view, name = 'edit_product_page'),
    path('product_details/<int:_product_id>/', product_details_view, name = 'product_details_page'),
    path('add_product_unit_price/', add_product_unit_price_view, name = 'add_product_unit_price_page'),
    # new
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
    path('customers/', customer_view, name = 'customer_page'),
    path('purchase/', purchase_order_view, name = 'purchase_order_page'),
    path('stock_transfer/', stock_transfer_view, name = 'stock_transfer_page'),
    path('delete_multiple/', DeleteMultipleSuppliers.as_view(), name = 'delete_multiple'),

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

    # Transfer Requests
    path('transfer_requests/', transfer_request_list, name='transfer_request_list'),
    path('transfer_requests/add/', add_transfer_request, name='add_transfer_request'),
    path('transfer_requests/<int:request_id>/', transfer_request_detail, name='transfer_request_detail'),
    path('transfer_requests/<int:request_id>/update/', update_transfer_request, name='update_transfer_request'),
    path('transfer_requests/<int:request_id>/approve/', approve_transfer_request, name='approve_transfer_request'),

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
]