from django.contrib import admin
from django.urls import path

from .views.general_views import index_view
from .views.product_views import manage_product_view, delete_category_view, add_product_view,add_category_view, edit_product_view, unit_of_measure_view, add_store_view, product_details_view,inventory_view, store_list_view, category_view
from .views.accounts_views import manage_accounts_view
from .views.general_views import login_view, sign_up_view, DeleteMultipleSuppliers
from .views.supplier_views import supplier_view, add_supplier_view
from .views.customer_view import customer_view, add_customer_view
from .views.transactions_views import purchase_order_view, sales_view, stock_transfer_view, pos_view, sales_return_view, create_sales_return_view, purchase_list_view, add_purchase_view



urlpatterns = [
    path('', index_view, name = 'index_page'),
    path('products/', manage_product_view, name ='products_page'),
    path('add_product/', add_product_view, name = 'add_products_page'),
    path('category/', category_view, name = 'category_page'),
    path('add_category/',add_category_view, name = "add_category_page"),
    path('supplier/', supplier_view, name = 'supplier_list_page'),
    path('store/', store_list_view, name = 'store_list_page'), 
    path('customers/', customer_view, name = 'customer_list_page'),
    path('sales/', sales_view, name = 'sales_list_page'),
    path('pos/', pos_view, name = 'pos_page'),
    path('sales_return_list/', sales_return_view, name = 'sales_return_page'),
    path('create_sales_return/', create_sales_return_view, name = 'create_sales_return_page'),
    path('purchase_list/', purchase_list_view, name = 'purchase_list_page'),
    path('add_purchase/', add_purchase_view, name = 'add_purchase_page'),
    path('add_customer/', add_customer_view, name = 'add_customer_page'),
    path('add_supplier/', add_supplier_view, name = 'add_supplier_page' ),
    path('add_store/', add_store_view, name = 'add_store_page')
]