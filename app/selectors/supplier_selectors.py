from app.models.suppliers import Supplier

def get_all_suppliers():
    return Supplier.objects.all()

def get_number_of_suppliers():
    return Supplier.objects.count()