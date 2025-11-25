from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from app.models.human_resource import UserProfile, Role, Employee
from app.forms.user_forms import UserCreateForm, UserEditForm, RoleAssignmentForm
from datetime import date

@login_required
def users_list_view(request):
    """List all users with pagination and filtering"""
    users = User.objects.all().select_related('profile', 'profile__employee').prefetch_related('groups', 'profile__roles')
    
    # Filtering
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            username__icontains=search_query
        ) | users.filter(
            email__icontains=search_query
        ) | users.filter(
            first_name__icontains=search_query
        ) | users.filter(
            last_name__icontains=search_query
        )
    
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    role_filter = request.GET.get('role', '')
    if role_filter:
        users = users.filter(profile__roles__id=role_filter).distinct()
    
    # Statistics
    total_users = users.count()
    active_users = users.filter(is_active=True).count()
    inactive_users = users.filter(is_active=False).count()
    users_with_roles = users.filter(profile__roles__isnull=False).distinct().count()
    
    # Pagination
    paginator = Paginator(users, 20)  # 20 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all roles for filter dropdown
    roles = Role.objects.filter(is_active=True)
    
    context = {
        'users': page_obj,
        'page_obj': page_obj,
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'users_with_roles': users_with_roles,
        'roles': roles,
        'search_query': search_query,
        'status_filter': status_filter,
        'role_filter': role_filter,
    }
    return render(request, 'users/users_list.html', context)

@login_required
def user_create_view(request):
    """Create a new user with optional employee creation"""
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            # Generate default password
            default_password = get_random_string(length=12)
            
            # Create user
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                password=default_password,
                is_active=True
            )
            
            # Handle employee linkage
            employee_option = form.cleaned_data.get('employee_option')
            employee = None
            
            if employee_option == 'existing':
                employee = form.cleaned_data.get('existing_employee')
                if employee:
                    employee.user = user
                    employee.save()
            elif employee_option == 'new':
                # Create new employee
                from app.models.organization import Branch
                employee = Employee.objects.create(
                    user=user,
                    gender=form.cleaned_data['gender'],
                    contact=form.cleaned_data['contact'],
                    branch=form.cleaned_data['branch'],
                    department=form.cleaned_data['department'],
                    designation=form.cleaned_data.get('designation'),
                    date_joined=form.cleaned_data['date_joined'] or date.today(),
                    address=form.cleaned_data.get('address', ''),
                    is_active=True
                )
            
            # Create or reuse user profile safely
            profile, created_profile = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'employee': employee,
                    'assigned_by': request.user
                }
            )

            # If a profile already existed, ensure it reflects the latest linkage info
            if not created_profile:
                updated = False
                if employee and profile.employee != employee:
                    profile.employee = employee
                    updated = True
                if profile.assigned_by != request.user:
                    profile.assigned_by = request.user
                    updated = True
                if updated:
                    profile.save()
            
            # Assign roles if provided (RBAC 2.0: multiple roles)
            roles = form.cleaned_data.get('roles', [])
            if roles:
                profile.roles.set(roles)
                profile.assigned_by = request.user
                profile.save()
                # Apply each role
                for role in roles:
                    role.apply_to_user(user)
            
            # Send email with default password
            try:
                send_mail(
                    subject='Your Account Has Been Created',
                    message=f'''Hello {user.get_full_name() or user.username},

Your account has been created in the system.

Username: {user.username}
Temporary Password: {default_password}

Please log in and change your password immediately.

Login URL: {request.build_absolute_uri('/login/')}

Best regards,
System Administrator''',
                    from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@example.com',
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                messages.success(request, f'User "{user.username}" created successfully. Password email sent.')
            except Exception as e:
                messages.warning(request, f'User "{user.username}" created successfully, but password email could not be sent: {str(e)}')
            
            return redirect('user_detail_page', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreateForm()
    
    context = {
        'form': form,
        'title': 'Create User',
    }
    return render(request, 'users/user_form.html', context)

@login_required
def user_edit_view(request, user_id):
    """Edit an existing user"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            # Update role assignment (RBAC 2.0: multiple roles)
            roles = form.cleaned_data.get('roles', [])
            profile, created = UserProfile.objects.get_or_create(user=user)
            if roles:
                profile.roles.set(roles)
                profile.assigned_by = request.user
                profile.save()
                # Apply each role
                for role in roles:
                    role.apply_to_user(user)
            else:
                # Remove all roles
                profile.roles.clear()
                profile.update_modules_from_roles()
            user = form.save()
            messages.success(request, f'User "{user.username}" has been updated successfully.')
            return redirect('user_detail_page', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserEditForm(instance=user)
    
    context = {
        'form': form,
        'user': user,
        'title': 'Edit User',
    }
    return render(request, 'users/user_form.html', context)

@login_required
def user_detail_view(request, user_id):
    """View user details"""
    user = get_object_or_404(User, id=user_id)
    
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = None
    
    context = {
        'user': user,
        'profile': profile,
    }
    return render(request, 'users/user_detail.html', context)

@login_required
def user_delete_view(request, user_id):
    """Delete or deactivate a user"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deleting yourself
    if user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('user_detail_page', user_id=user.id)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'deactivate')
        
        if action == 'delete':
            # Check if user is the last user with access to critical modules
            # This is a defensive check - you can customize based on your needs
            username = user.username
            user.delete()
            messages.success(request, f'User "{username}" has been deleted successfully.')
        else:
            # Deactivate
            user.is_active = False
            user.save()
            messages.success(request, f'User "{user.username}" has been deactivated.')
        
        return redirect('users_list_page')
    
    context = {
        'user': user,
    }
    return render(request, 'users/user_delete_confirm.html', context)

@login_required
def user_assign_role_view(request, user_id):
    """Assign roles to a user (RBAC 2.0: supports multiple roles)"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = RoleAssignmentForm(request.POST, user=user)
        if form.is_valid():
            roles = form.cleaned_data['roles']
            
            # Get or create user profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.roles.set(roles)
            profile.assigned_by = request.user
            profile.save()
            
            # Apply each role to user
            for role in roles:
                role.apply_to_user(user)
            
            role_names = ", ".join([r.name for r in roles])
            messages.success(request, f'Role(s) "{role_names}" assigned to {user.username}.')
            return redirect('user_detail_page', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RoleAssignmentForm(user=user)
    
    context = {
        'form': form,
        'user': user,
    }
    return render(request, 'users/user_assign_role.html', context)

@login_required
@require_http_methods(["POST"])
def user_unassign_role_view(request, user_id, role_id=None):
    """Unassign role(s) from a user (RBAC 2.0)"""
    user = get_object_or_404(User, id=user_id)
    
    try:
        profile = user.profile
        if role_id:
            # Unassign specific role
            role = get_object_or_404(Role, id=role_id)
            if role in profile.roles.all():
                profile.roles.remove(role)
                profile.update_modules_from_roles()
                messages.success(request, f'Role "{role.name}" has been unassigned from {user.username}.')
            else:
                messages.info(request, f'User does not have role "{role.name}" assigned.')
        else:
            # Unassign all roles
            if profile.roles.exists():
                role_names = ", ".join([r.name for r in profile.roles.all()])
                profile.roles.clear()
                profile.update_modules_from_roles()
                messages.success(request, f'All roles ({role_names}) have been unassigned from {user.username}.')
            else:
                messages.info(request, 'User does not have any roles assigned.')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile does not exist.')
    
    return redirect('user_detail_page', user_id=user.id)

