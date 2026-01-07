# views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.models import User
from app.models.human_resource import UserProfile, Employee
import json

@login_required
@csrf_protect
def profile_view(request):
    """
    View-only user profile with password reset capability
    """
    user = request.user
    
    # Debug: # print request info
    # print(f"\n=== PROFILE VIEW ACCESSED ===")
    # print(f"User: {user.username}")
    # print(f"Method: {request.method}")
    # print(f"POST keys: {list(request.POST.keys()) if request.method == 'POST' else 'N/A'}")
    
    # Get user profile
    profile = UserProfile.objects.filter(user=user).first()
    
    # Get employee profile with related data
    employee = None
    employee_data = {}
    
    try:
        employee = Employee.objects.select_related(
            'department', 'designation', 'branch'
        ).get(user=user)
        
        # Extract employee data for template
        employee_data = {
            'contact': employee.contact,
            'department_name': employee.department.name if employee.department else 'N/A',
            'designation_title': employee.designation.title if employee.designation else 'N/A',
            'branch_name': employee.branch.name if employee.branch else 'N/A',
            'date_joined': employee.date_joined,
            'is_active': employee.is_active,
            'address': employee.address,
            'photo': employee.photo
        }
    except Employee.DoesNotExist:
        employee_data = {
            'contact': 'N/A',
            'department_name': 'N/A',
            'designation_title': 'N/A',
            'branch_name': 'N/A',
            'date_joined': 'N/A',
            'is_active': False,
            'address': 'N/A',
            'photo': None
        }
    
    # Handle password change
    if request.method == 'POST':
        # print(f"\n=== PROCESSING POST REQUEST ===")
        
        # Check if update_security button was clicked
        # print(f"Checking for 'update_security' in POST...")
        # print(f"All POST keys: {dict(request.POST)}")
        
        # The issue might be that 'update_security' is not in the POST dict as a key
        # It might be submitted as a button value. Let's check differently:
        if 'update_security' in request.POST:
            # print("✓ 'update_security' found in POST keys")
            
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            
            # Debug: # print received data
            # print(f"\n=== PASSWORD CHANGE ATTEMPT ===")
            # print(f"User: {user.username}")
            # print(f"Current password length: {len(current_password)}")
            # print(f"New password length: {len(new_password)}")
            # print(f"Confirm password length: {len(confirm_password)}")
            
            # Validate password change
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
                    # print(f"Validation error: {error}")
            else:
                # Check current password
                # print(f"Checking current password...")
                if user.check_password(current_password):
                    # print("✓ Current password is correct")
                    try:
                        # Change password
                        user.set_password(new_password)
                        user.save()
                        update_session_auth_hash(request, user)  # Keep user logged in
                        messages.success(request, 'Password updated successfully!')
                        # print(f"✓ Password updated successfully for {user.username}")
                        
                        # Redirect using the correct URL name
                        return redirect('profile_details')
                        
                    except Exception as e:
                        messages.error(request, f'Error updating password: {str(e)}')
                        # print(f"✗ Error updating password: {str(e)}")
                else:
                    messages.error(request, 'Current password is incorrect.')
                    # print(f"✗ Current password is incorrect for {user.username}")
        else:
            pass
            # print("✗ 'update_security' NOT found in POST keys")
            # print(f"Available keys: {list(request.POST.keys())}")
    
    # Create context
    context = {
        'user': user,
        'profile': profile,
        'employee': employee,
        'employee_data': employee_data,
        'activity_chart_data': json.dumps({
            'labels': [],
            'data': []
        })
    }
    
    return render(request, 'users/profile.html', context)