from app.models.suppliers import Supplier

def get_all_suppliers():
    return Supplier.objects.all()