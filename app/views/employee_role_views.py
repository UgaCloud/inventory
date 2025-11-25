"""
Views for managing employee roles (RBAC 2.0)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from app.models.human_resource import Employee, Role, UserProfile
from django.contrib.auth.models import User

@login_required
def employee_manage_roles_view(request, employee_id):
    """Manage roles for a specific employee (RBAC 2.0)"""
    employee = get_object_or_404(Employee, id=employee_id)
    
    # Get user profile if employee has a user
    profile = None
    if employee.user:
        try:
            profile = employee.user.profile
        except UserProfile.DoesNotExist:
            pass
    
    if request.method == 'POST':
        role_ids = request.POST.getlist('roles')
        roles = Role.objects.filter(id__in=role_ids, is_active=True)
        
        if not employee.user:
            messages.error(request, 'Employee must have a user account to assign roles.')
            return redirect('employee_manage_roles_page', employee_id=employee_id)
        
        # Get or create profile
        if not profile:
            profile = UserProfile.objects.create(user=employee.user, employee=employee)
        
        # Update roles
        profile.roles.set(roles)
        profile.assigned_by = request.user
        profile.save()
        
        # Apply each role
        for role in roles:
            role.apply_to_user(employee.user)
        
        role_names = ", ".join([r.name for r in roles]) if roles else "None"
        messages.success(request, f'Roles updated for {employee.user.get_full_name() or employee.user.username}: {role_names}')
        return redirect('employee_manage_roles_page', employee_id=employee_id)
    
    # Get all available roles
    all_roles = Role.objects.filter(is_active=True)
    current_role_ids = list(profile.roles.values_list('id', flat=True)) if profile else []
    
    context = {
        'employee': employee,
        'profile': profile,
        'all_roles': all_roles,
        'current_role_ids': current_role_ids,
    }
    return render(request, 'employees/employee_manage_roles.html', context)


