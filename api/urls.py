from django.urls import path
from . import views

urlpatterns = [
    path('transfer-request/create/', views.CreateTransferRequestAPI.as_view(), name='api_transfer_request_create'),
    path('transfer-request/approve/', views.ApproveTransferRequestAPI.as_view(), name='api_transfer_request_approve'),
    path('stock-transfer/create/', views.CreateStockTransferAPI.as_view(), name='api_stock_transfer_create'),
    path('stock-transfer/complete/', views.CompleteStockTransferAPI.as_view(), name='api_stock_transfer_complete'),
    path('stock-transfer/start/', views.StartStockTransferAPI.as_view(), name='api_stock_transfer_start'),
    path('store/<int:store_id>/stock/<int:product_id>/available/', views.AvailableStockAPI.as_view(), name='api_available_stock'),
]
