from django.contrib import admin

from app.models.products import *
from app.models.transactions import *
from app.models.suppliers import *
from app.models.customers import *

admin.site.register(Product)
admin.site.register(Category)
admin.site.register(UnitOfMeasure)
admin.site.register(ProductUnitPrice)
admin.site.register(PurchaseOrder)
admin.site.register(PurchaseOrderItem)
admin.site.register(Sales)
admin.site.register(SalesItem)
admin.site.register(StockMovement)
admin.site.register(Inventory)
admin.site.register(StockTransfer)
admin.site.register(Supplier)
admin.site.register(Customer)
admin.site.register(StoreLocation)
admin.site.register(Branch)
admin.site.register(TransferRequest)
admin.site.register(TransferRequestItem)
admin.site.register(StockTransferItem)

# admin.site.register(StockAdjustment)
# admin.site.register(StockAdjustmentItem)
# admin.site.register(StockReturn)
# admin.site.register(StockReturnItem)
# admin.site.register(StockDamage)
# admin.site.register(StockDamageItem)
