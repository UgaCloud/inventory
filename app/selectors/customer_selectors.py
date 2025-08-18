from app.models.customers import Customer, CustomerLedger

def get_all_customers():
    return Customer.objects.all()

def get_number_of_customers():
    return Customer.objects.count()

def get_all_customer_ledgers():
    return CustomerLedger.objects.all()

def get_customer_ledger(ledger_id):
    return CustomerLedger.objects.filter(pk=ledger_id).first()

def get_ledgers_for_customer(customer):
    return CustomerLedger.objects.filter(customer=customer).order_by('-date')