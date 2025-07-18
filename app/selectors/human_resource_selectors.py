from django.shortcuts import get_object_or_404
from app.models.human_resource import *

def get_department_by_id(department_id):
    department = get_object_or_404(Department, pk = department_id)
    return department