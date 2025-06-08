from app.models.customers import Customer

def get_all_customers():
    return Customer.objects.all()