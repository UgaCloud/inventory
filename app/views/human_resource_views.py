from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from app.forms.human_resource_forms import *
from app.selectors.human_resource_selectors import *

@login_required
def employee_view(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Employee has been added successfully')
        else:
            messages.error(request, 'There was an error adding the employee')
    else:
        form = EmployeeForm()
    
    employees = Employee.objects.select_related('branch').select_related('department').select_related('designation').all()

    context = {
        'employees':employees,
        'form':form
    }
    return render(request, 'human_resource/employee.html', context)

@login_required
def edit_employee_view(request, employee_id):
    employee = get_employee_by_id(employee_id)

    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance = employee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Employee successfully edited')
        else:
            messages.error(request, 'An error occured, unable to update the employee')
    return redirect(employee_view)

@login_required
def department_view(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Department has been added succesfully')
        else:
            messages.error(request, 'An error occured, unable to add department')
    else:
        form = DepartmentForm()
    
    departments = Department.objects.all()

    context = {
        'departments':departments,
        'form':form
    }

    return render(request, 'human_resource/department.html', context)

@login_required
def edit_department_view(request, department_id):
    department = get_department_by_id(department_id) #get_department() is in the human resource selectors

    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance = department)

        if form.is_valid():
            form.save()
            messages.success(request, 'The department has been updated successfully')
            return redirect(department_view)
        else:
            messages.error(request, 'An error occured, unable to update department')

    form = Department(instance = department)
    return redirect(department_view)

@login_required
def designation_view(request):
    if request.method == 'POST':
        form = DesignationForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'The designation has been created successfully')
        else:
            messages.error(request, 'An error occured, unsable to create the designation')

    else:
        form = DesignationForm()
    
    designations = Designation.objects.all()

    context = {
        'designations':designations,
        'form':form
    }

    return render(request, 'human_resource/designation.html', context)

@login_required
def edit_designation_view(request, designation_id):
    designation = get_designation_by_id(designation_id)

    if request.method == 'POST':
        form = DesignationForm(request.POST, instance = designation)

        if form.is_valid():
            form.save()
            messages.success(request, 'Designation has been updated successfully')
        else:
            messages.error(request, 'An error occured, unable to update the designation')
    return redirect(designation_view)