from app.models.organization import *

def get_branches():
    return Branch.objects.all()

def get_branch(branch_id):
    return Branch.objects.get(id = branch_id)

def get_branch_by_name(name):
    return Branch.objects.filter(name=name)

def get_active_branches():
    return Branch.objects.filter(is_active=True)

def get_branches_by_city(city):
    return Branch.objects.filter(city=city)

def branch_exists(branch_id):
    return Branch.objects.filter(id=branch_id).exists()

def count_branches():
    return Branch.objects.count()
