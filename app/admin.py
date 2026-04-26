from django.contrib import admin

from app.models.organization import *
from app.models.products import *
from app.models.transactions import *
from app.models.suppliers import *
from app.models.customers import *
from app.models.finance import *
from app.models.expense import *
from app.models.human_resource import Employee
from app.forms.human_resource_forms import EmployeeForm


# Generic admin for all models

def get_admin_for_model(model):
    class CustomAdmin(admin.ModelAdmin):
        list_display = [field.name for field in model._meta.fields]
        search_fields = [field.name for field in model._meta.fields if field.get_internal_type() in ['CharField', 'TextField', 'EmailField']]
        list_filter = [field.name for field in model._meta.fields if field.get_internal_type() in ['BooleanField', 'NullBooleanField', 'ForeignKey'] and hasattr(model, field.name)]
    return CustomAdmin


class EmployeeAdmin(admin.ModelAdmin):
    form = EmployeeForm
    list_display = ('first_name', 'last_name', 'email', 'department', 'designation', 'user', 'is_active')
    search_fields = ('first_name', 'last_name', 'email', 'user__username')
    list_filter = ('department', 'designation', 'is_active')


# Register all models with a custom admin except Employee
admin.site.register(Product, get_admin_for_model(Product))
admin.site.register(Automotive, get_admin_for_model(Automotive))
admin.site.register(Category, get_admin_for_model(Category))
admin.site.register(UnitOfMeasure, get_admin_for_model(UnitOfMeasure))
admin.site.register(ProductUnitPrice, get_admin_for_model(ProductUnitPrice))
admin.site.register(PurchaseOrder, get_admin_for_model(PurchaseOrder))
admin.site.register(PurchaseOrderItem, get_admin_for_model(PurchaseOrderItem))
admin.site.register(Sales, get_admin_for_model(Sales))
admin.site.register(SalesItem, get_admin_for_model(SalesItem))
admin.site.register(StockMovement, get_admin_for_model(StockMovement))
admin.site.register(Inventory, get_admin_for_model(Inventory))
admin.site.register(StockTransfer, get_admin_for_model(StockTransfer))
admin.site.register(StoreLocation, get_admin_for_model(StoreLocation))
admin.site.register(Branch, get_admin_for_model(Branch))
admin.site.register(TransferRequest, get_admin_for_model(TransferRequest))
admin.site.register(TransferRequestItem, get_admin_for_model(TransferRequestItem))
admin.site.register(StockTransferItem, get_admin_for_model(StockTransferItem))
admin.site.register(OrganizationSetting, get_admin_for_model(OrganizationSetting))
admin.site.register(Currency, get_admin_for_model(Currency))
admin.site.register(Expense, get_admin_for_model(Expense))
admin.site.register(ExpenseCategory, get_admin_for_model(ExpenseCategory))
admin.site.register(CashFlow, get_admin_for_model(CashFlow))
admin.site.register(DailyCashSummary, get_admin_for_model(DailyCashSummary))
admin.site.register(BankAccount, get_admin_for_model(BankAccount))
admin.site.register(BankTransaction, get_admin_for_model(BankTransaction))
admin.site.register(PaymentMethod, get_admin_for_model(PaymentMethod))
admin.site.register(Supplier, get_admin_for_model(Supplier))
admin.site.register(Customer, get_admin_for_model(Customer))
admin.site.register(CustomerLedger, get_admin_for_model(CustomerLedger))
admin.site.register(Payment, get_admin_for_model(Payment))
admin.site.register(InventoryBatch, get_admin_for_model(InventoryBatch))
admin.site.register(Employee, EmployeeAdmin)
admin.site.register(StockAdjustmentItem, get_admin_for_model(StockAdjustmentItem))



