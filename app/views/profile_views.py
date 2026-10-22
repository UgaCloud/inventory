"""Views for the signed-in user's own profile."""
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect

from app.models.audit import AuditLog
from app.models.human_resource import Employee, UserProfile
from app.models.preferences import UserPreference


def _initials(user):
    """Fallback avatar label (one or two letters) for a user."""
    name = (user.get_full_name() or user.username or '').strip()
    parts = [part for part in name.split() if part]
    if not parts:
        return (user.username[:2] or '?').upper()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _employee_data(employee):
    """Flatten an employee row into template friendly values."""
    if employee is None:
        return {
            'contact': 'N/A',
            'department_name': 'N/A',
            'designation_title': 'N/A',
            'branch_name': 'N/A',
            'date_joined': None,
            'is_active': False,
            'address': 'N/A',
            'photo': None,
        }
    return {
        'contact': employee.contact or 'N/A',
        'department_name': employee.department.name if employee.department else 'N/A',
        'designation_title': employee.designation.title if employee.designation else 'N/A',
        'branch_name': employee.branch.name if employee.branch else 'N/A',
        'date_joined': employee.date_joined,
        'is_active': employee.is_active,
        'address': employee.address or 'N/A',
        'photo': employee.photo,
    }


@login_required
@csrf_protect
def profile_view(request):
    """Show the signed-in user's profile and allow a password change."""
    user = request.user

    profile = UserProfile.objects.filter(user=user).first()

    employee = None
    try:
        employee = Employee.objects.select_related(
            'department', 'designation', 'branch'
        ).get(user=user)
    except Employee.DoesNotExist:
        employee = None

    employee_data = _employee_data(employee)

    # Handle password change
    if request.method == 'POST' and 'update_security' in request.POST:
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        validation_errors = []
        if not current_password:
            validation_errors.append('Please enter your current password.')
        if not new_password:
            validation_errors.append('Please enter a new password.')
        elif len(new_password) < 8:
            validation_errors.append('Password must be at least 8 characters long.')
        if new_password != confirm_password:
            validation_errors.append('New passwords do not match.')

        if validation_errors:
            for error in validation_errors:
                messages.error(request, error)
        elif not user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
        else:
            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)  # keep the user signed in
            messages.success(request, 'Password updated successfully!')
            return redirect('profile_details')

    roles = list(profile.roles.all()) if profile is not None else []
    preference = UserPreference.for_user(user)
    sign_ins = AuditLog.objects.filter(
        actor=user,
        action__in=[AuditLog.Action.LOGIN, AuditLog.Action.LOGIN_FAILED],
    )[:8]

    business = None
    if profile is not None:
        business = profile.business
    if business is None:
        from app.models.tenancy import current_business
        business = current_business(user)

    context = {
        'user': user,
        'profile': profile,
        'employee': employee,
        'employee_data': employee_data,
        'roles': roles,
        'preference': preference,
        'sign_ins': sign_ins,
        'initials': _initials(user),
        'business': business,
        'business_name': getattr(business, 'name', ''),
    }

    return render(request, 'users/profile.html', context)
