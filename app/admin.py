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


class EmployeeAdmin(admin.ModelAdmin):
    form = EmployeeForm
    list_display = ('first_name', 'last_name', 'email', 'department', 'designation', 'user', 'is_active')
    search_fields = ('first_name', 'last_name', 'email', 'user__username')
    list_filter = ('department', 'designation', 'is_active')


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
admin.site.register(CustomerLedger)
admin.site.register(Payment)
admin.site.register(StoreLocation)
admin.site.register(Branch)
admin.site.register(TransferRequest)
admin.site.register(TransferRequestItem)
admin.site.register(StockTransferItem)
admin.site.register(OrganizationSetting)
admin.site.register(Currency)
admin.site.register(Expense)
admin.site.register(ExpenseCategory)
admin.site.register(CashFlow)
admin.site.register(DailyCashSummary)
admin.site.register(BankAccount)
admin.site.register(BankTransaction)
admin.site.register(PaymentMethod)
admin.site.register(Employee, EmployeeAdmin)


# admin.site.register(StockAdjustment)
# admin.site.register(StockAdjustmentItem)
# admin.site.register(StockReturn)
# admin.site.register(StockReturnItem)
# admin.site.register(StockDamage)
# admin.site.register(StockDamageItem)
