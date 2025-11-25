from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from app.models.human_resource import Role, RoleModule, RoleDeletionLog, UserProfile
from app.forms.role_forms import RoleCreateForm, RoleEditForm, RoleDeleteForm

from app.models.human_resource import get_module_name_by_id
from app.utils.dashboard_assignment import get_dashboards_for_modules

@login_required
def roles_list_view(request):
    """List all roles with pagination and filtering"""
    roles = Role.objects.all().prefetch_related('modules', 'assigned_profiles')
    
    # Filtering
    search_query = request.GET.get('search', '')
    if search_query:
        roles = roles.filter(name__icontains=search_query)
    
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        roles = roles.filter(is_active=True)
    elif status_filter == 'inactive':
        roles = roles.filter(is_active=False)
    
    # Statistics
    total_roles = roles.count()
    active_roles = roles.filter(is_active=True).count()
    inactive_roles = roles.filter(is_active=False).count()
    system_roles = roles.filter(is_system_role=True).count()
    
    # Pagination
    paginator = Paginator(roles, 12)  # 12 roles per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'roles': page_obj,
        'page_obj': page_obj,
        'total_roles': total_roles,
        'active_roles': active_roles,
        'inactive_roles': inactive_roles,
        'system_roles': system_roles,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'roles/roles_list.html', context)

@login_required
def role_create_view(request):
    """Create a new role"""
    if request.method == 'POST':
        form = RoleCreateForm(request.POST)
        if form.is_valid():
            role = form.save()
            messages.success(request, f'Role "{role.name}" has been created successfully.')
            return redirect('role_detail_page', role_id=role.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RoleCreateForm()
    
    context = {
        'form': form,
        'title': 'Create Role',
        'action': 'create',
    }
    return render(request, 'roles/role_form.html', context)

@login_required
def role_edit_view(request, role_id):
    """Edit an existing role"""
    role = get_object_or_404(Role, id=role_id)
    
    if request.method == 'POST':
        form = RoleEditForm(request.POST, instance=role)
        if form.is_valid():
            role = form.save()
            messages.success(request, f'Role "{role.name}" has been updated successfully.')
            return redirect('role_detail_page', role_id=role.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RoleEditForm(instance=role)
    
    context = {
        'form': form,
        'role': role,
        'title': 'Edit Role',
        'action': 'edit',
    }
    return render(request, 'roles/role_form.html', context)

@login_required
def role_detail_view(request, role_id):
    """View role details"""
    role = get_object_or_404(Role, id=role_id)
    
    # Get modules assigned to this role
    modules = role.modules.all().order_by('module_id')
    
    # Get users with this role (RBAC 2.0: M2M)
    users = role.assigned_profiles.select_related('user', 'employee').prefetch_related('roles').all()
    
    context = {
        'role': role,
        'modules': modules,
        'users': users,
        'user_count': users.count(),
        'module_count': modules.count(),
            # Add dashboards assigned to this role
            'dashboards': get_dashboards_for_modules(
                [m.module_id for m in modules]
            ),
    }
    return render(request, 'roles/role_detail.html', context)

@login_required
def role_delete_view(request, role_id):
    """Delete a role with validation"""
    role = get_object_or_404(Role, id=role_id)
    
    # Check if role can be deleted (RBAC 2.0: check M2M)
    user_count = role.assigned_profiles.count()
    can_delete = user_count == 0 and not role.is_system_role
    
    if request.method == 'POST':
        form = RoleDeleteForm(request.POST, role=role)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            
            # Log deletion before deleting
            RoleDeletionLog.log_from_role(role, reason, user=request.user)
            
            role_name = role.name
            role.delete()
            
            messages.success(request, f'Role "{role_name}" has been deleted successfully.')
            return redirect('roles_list_page')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RoleDeleteForm(role=role)
    
    context = {
        'role': role,
        'form': form,
        'user_count': user_count,
        'can_delete': can_delete,
    }
    return render(request, 'roles/role_delete_confirm.html', context)

@login_required
@require_http_methods(["POST"])
def role_assign_to_user_view(request, role_id, user_id):
    """Assign a role to a user (RBAC 2.0: adds to M2M)"""
    role = get_object_or_404(Role, id=role_id)
    user = get_object_or_404(request.user.__class__, id=user_id)
    
    # Get or create user profile
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Assign role (RBAC 2.0: add to M2M)
    if role not in profile.roles.all():
        profile.roles.add(role)
        profile.assigned_by = request.user
        profile.save()
        
        # Apply role to user (updates permissions and modules)
        role.apply_to_user(user)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Role "{role.name}" has been assigned to {user.username}'
            })
        
        messages.success(request, f'Role "{role.name}" has been assigned to {user.username}.')
    else:
        messages.info(request, f'User {user.username} already has role "{role.name}".')
    
    return redirect('role_detail_page', role_id=role.id)

@login_required
@require_http_methods(["POST"])
def role_unassign_from_user_view(request, role_id, user_id):
    """Unassign a role from a user (RBAC 2.0: removes from M2M)"""
    role = get_object_or_404(Role, id=role_id)
    user = get_object_or_404(request.user.__class__, id=user_id)
    
    try:
        profile = UserProfile.objects.get(user=user)
        if role in profile.roles.all():
            profile.roles.remove(role)
            profile.update_modules_from_roles()
            
            # Remove from group
            if role.group:
                user.groups.remove(role.group)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Role "{role.name}" has been unassigned from {user.username}'
                })
            
            messages.success(request, f'Role "{role.name}" has been unassigned from {user.username}.')
        else:
            messages.error(request, 'User does not have this role assigned.')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile does not exist.')
    
    return redirect('role_detail_page', role_id=role.id)

@login_required
def role_bulk_assign_view(request, role_id):
    """Bulk assign a role to multiple users (RBAC 2.0)"""
    role = get_object_or_404(Role, id=role_id)
    from django.contrib.auth.models import User
    
    if request.method == 'POST':
        user_ids = request.POST.getlist('user_ids')
        if not user_ids:
            messages.error(request, 'Please select at least one user.')
            return redirect('role_bulk_assign_page', role_id=role_id)
        
        users = User.objects.filter(id__in=user_ids)
        assigned_count = 0
        
        for user in users:
            profile, created = UserProfile.objects.get_or_create(user=user)
            if role not in profile.roles.all():
                profile.roles.add(role)
                profile.assigned_by = request.user
                profile.save()
                role.apply_to_user(user)
                assigned_count += 1
        
        messages.success(request, f'Role "{role.name}" has been assigned to {assigned_count} user(s).')
        return redirect('role_detail_page', role_id=role_id)
    
    # Get all users
    users = User.objects.all().select_related('profile').prefetch_related('profile__roles')
    # Filter out users who already have this role
    users_with_role = role.assigned_profiles.values_list('user_id', flat=True)
    
    context = {
        'role': role,
        'users': users,
        'users_with_role': users_with_role,
    }
    return render(request, 'roles/role_bulk_assign.html', context)
