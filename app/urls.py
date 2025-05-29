from django.contrib import admin
from django.urls import path

from .views.general_views import index_view
from .views.product_views import manage_product_view

urlpatterns = [
    path('', index_view, name='index_page'),
    path('products/', manage_product_view, name='manage_products_page')
]