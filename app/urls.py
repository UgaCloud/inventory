from django.contrib import admin
from django.urls import path

from .views.general_views import index_view
from .views.product_views import manage_product_view
from .views.accounts_views import manage_accounts_view

urlpatterns = [
    path('index.html', index_view, name='index_page'),
    path('products.html', manage_product_view, name='products_page'),
    path('accounts.html', manage_accounts_view, name='accounts_page'),

]