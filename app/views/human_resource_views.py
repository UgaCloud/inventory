from django.shortcuts import render, redirect
from app.forms.human_resource_forms import *
from app.selectors.human_resource_selectors import *


def employee_view(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = EmployeeForm()
    
    employees = Employee.objects.select_related('branch').select_related('department').select_related('designation').all()

    context = {
        'employees':employees,
        'form':form
    }


    
    return render(request, 'human_resource/employee.html', context)

def edit_employee_view(request, employee_id):
    return redirect(employee_view)

def department_view(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = DepartmentForm()
    
    departments = Department.objects.all()

    context = {
        'departments':departments,
        'form':form
    }

    return render(request, 'human_resource/department.html', context)

def edit_department_view(request, department_id):
    department = get_department_by_id(department_id) #get department method is in the human resource selectors
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance = department)
        if form.is_valid():
            form.save()
    form = Department()
    return redirect(department_view)

def designation_view(request):
    if request.method == 'POST':
        form = DesignationForm(request.POST)

        if form.is_valid():
            form.save()
    else:
        form = DesignationForm()
    
    designations = Designation.objects.all()

    context = {
        'designations':designations,
        'form':form
    }

    return render(request, 'human_resource/designation.html', context)

def edit_designation_view(request, designation_id):
    return redirect(designation_view)