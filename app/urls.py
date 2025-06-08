from django.contrib import admin
from django.urls import path

from .views.general_views import index_view
from .views.product_views import manage_product_view, delete_category_view, add_product_view,add_category_view, edit_product_view, unit_of_measure_view, product_details_view,inventory_view, store_view
from .views.accounts_views import manage_accounts_view
from .views.general_views import login_view, sign_up_view
from .views.supplier_views import supplier_view
from .views.customer_view import customer_view
from .views.transactions_views import purchase_order_view, sales_view, stock_transfer_view



urlpatterns = [
    path('', index_view, name = 'index_page'),
    path('login/', login_view, name = 'login_page'),
    path('sign_up/', sign_up_view, name = 'sign_up_page'),
    path('products/', manage_product_view, name ='products_page'),
    path('accounts/', manage_accounts_view, name='accounts_page'),
    path('add_product/', add_product_view, name = 'add_products_page'),
    path('add_category/', add_category_view, name = 'add_category_page'),
    path('delete_category/<int:category_id>/',delete_category_view, name = 'delete_category'),
    path('edit_product/<int:product_id>', edit_product_view, name = 'edit_product_page'),
    path('unit_of_measure/', unit_of_measure_view, name = 'unit_of_measure_page'),
    path('supplier/', supplier_view, name = 'supplier_page'),
    path('product_details/<int:_product_id>/', product_details_view, name = 'product_details_page'),
    path('inventory/', inventory_view, name = 'inventory_page'),
    path('store/', store_view, name = 'store_page'),
    path('customers/', customer_view, name = 'customer_page'),
    path('purchase/', purchase_order_view, name = 'purchase_order_page'),
    path('sales/', sales_view, name = 'sales_page'),
    path('stock_transfer/', stock_transfer_view, name = 'stock_transfer_page'),

]