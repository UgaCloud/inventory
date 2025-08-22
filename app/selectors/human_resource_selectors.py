from django.shortcuts import get_object_or_404
from app.models.human_resource import *

def get_all_employees():
    employees = Employee.objects.all()
    return employees

def get_employee_by_id(employee_id):
    employee = get_object_or_404(Employee, pk = employee_id)
    return employee
def get_all_departments():
    departments = Department.objects.all()
    return departments

def get_department_by_id(department_id):
    department = get_object_or_404(Department, pk = department_id)
    return department

def get_designation_by_id(designation_id):
    designation = get_object_or_404(Designation, pk = designation_id)
    return designation

