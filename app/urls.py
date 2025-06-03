from django.contrib import admin
from django.urls import path

from .views.general_views import index_view
from .views.product_views import manage_product_view, delete_category_view, add_product_view, delete_product_view, add_category_view, edit_product_view, unit_of_measure_view
from .views.accounts_views import manage_accounts_view

from .views.general_views import login_view, sign_up_view


urlpatterns = [
    path('', index_view, name = 'index_page'),
    path('products/', manage_product_view, name ='products_page'),
    path('accounts/', manage_accounts_view, name='accounts_page'),
    path('add_product/', add_product_view, name = 'add_products_page'),
    path('add_category/', add_category_view, name = 'add_category_page'),
    path('delete_products/<int:product_id>/', delete_product_view, name = 'delete_product'),
    path('delete_category/<int:category_id>/',delete_category_view, name = 'delete_category'),
    path('login/', login_view, name = 'login_page'),
    path('sign_up/', sign_up_view, name = 'sign_up_page'),
    path('edit_product/<int:product_id>', edit_product_view, name = 'edit_product_page'),
    path('unit_of_measure/', unit_of_measure_view, name = 'unit_of_measure_page'),

]