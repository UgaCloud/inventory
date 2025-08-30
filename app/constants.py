
COUNTRIES = (
        ("UG", "Uganda"),
        ("KE", "Kenya"),
        ("TZ", "Tanzania"),
        ("RD", "Rwanda"),
        ("BD", "Burundi"),
        ("SD", "South Sudan")
    )


GENDERS = [
    ("M", "Male"),
    ("F", "Female")
]

MARITAL_STATUS = [
    ("M", "Married"),
    ("U", "Unmarried")
]

EMPLOYEE_STATUS = [
        ('Active', 'Active'),
        ('On Leave', 'On Leave'),
        ('Retired', 'Retired')
    ]

PURCHASE_ORDER_OPTIONS = [
        ('PENDING', 'Pending'), 
        ('RECEIVED', 'Received')
    ]

SALE_ORDER_OPTIONS = [
        ('PENDING', 'Pending'), 
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('FULFILLED', 'Fulfilled')
    ]

STOCK_MOVEMENT_OPTIONS = [
    ('Initial Stock', 'Initial Stock'), 
    ('Stocked', 'Stocked'), 
    ('Sold', 'Sold'), 
    ('In', 'In'), 
    ('Out', 'Out'), 
    ('Transfered', 'Transfered'),
    ('Returned', 'Returned'),
    ('Expired', 'Expired'),
    ('Damaged', 'Damaged'),
    ('Stolen', 'Stolen'),
    ('Removed', 'Removed'),
]

PAYMENT_METHODS = [
    ('Cash', 'Cash'),
    ('Mobile Money', 'Mobile Money'),
    ('Bank', 'Bank')
]

PAYMENT_STATUS = [
    ('Pending', 'Pending'), 
    ('Paid', 'Paid')
]

CASHFLOW_TYPES = [
        ('SALE', 'Sale'),
        ('PURCHASE', 'Purchase'),
        ('EXPENSE', 'Expense'),
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
    ]

TRANSACTION_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('TRANSFER_IN', 'Transfer In'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('PAYMENT', 'Payment'),
        ('RECEIPT', 'Receipt'),
        ('CHARGE', 'Bank Charge'),
        ('INTEREST', 'Interest'),
    ]

CURRENCY_CHOICES = [
    ('UGX', 'Ugandan Shilling'),
    ('KSH', 'Kenyan Shilling'),
]

SUCCESS_ADD_MESSAGE = "Record Saved!"

SUCCESS_EDIT_MESSAGE = "Changes Saved"
SUCCESS_BULK_ADD_MESSAGE = "All Record Saved!"

CONFIRMATION_MESSAGE ="Are you sure you want to delete this field?"
DELETE_MESSAGE = "Record Deleted"
FAILURE_LOGIN_MESSAGE="Invalid username or password"
FAILURE_MESSAGE = "Something Went Wrong!, Check your inputs and Try again"

INTEGRITY_ERROR_MESSAGE = "The record you tried to add is a duplicate or contains duplicate values" \
                          " for unique fields."

INVALID_VALUE_MESSAGE = "One or more values provided is/are invalid or duplicate for unique fields."


PALETTE = ['#465b65', '#184c9c', '#d33035', '#ffc107', '#28a745', '#6f7f8c', '#6610f2', '#6e9fa5', '#fd7e14',
           '#e83e8c', '#17a2b8', '#6f42c1']
