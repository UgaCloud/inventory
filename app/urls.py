from django.contrib import admin
from django.urls import path

from .views.general_views import index_view
from .views.product_views import manage_product_view, add_product_view 
from .views.accounts_views import manage_accounts_view
from .views.category_views import add_category_view, delete_category_view


urlpatterns = [
    path('', index_view, name='index_page'),
    path('products/', manage_product_view, name='products_page'),
    path('accounts/', manage_accounts_view, name='accounts_page'),
    path('add_product/', add_product_view, name = 'add_products_page'),
    path('add_category/', add_category_view, name = 'add_category_page'),
    path('products/<int:category_id>/',delete_category_view, name = 'delete_category'),

]