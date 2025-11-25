# Role Management System Documentation

## Overview

This document describes the complete Role Management + User/Employee Management System implemented in the Django enterprise inventory system. The system provides module-based access control, role assignment, and comprehensive user management.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Role Management](#role-management)
3. [User Management](#user-management)
4. [Permission Enforcement](#permission-enforcement)
5. [Navigation Filtering](#navigation-filtering)
6. [Module System](#module-system)
7. [Signals and Automation](#signals-and-automation)
8. [Usage Examples](#usage-examples)

---

## System Architecture

### Models

#### Role Model
- **Location**: `app/models/human_resource.py`
- **Purpose**: Defines roles with module access permissions
- **Key Fields**:
  - `name`: Role name (unique)
  - `description`: Role description
  - `is_staff`, `is_active`, `is_superuser`: Django permission flags
  - `department`, `designation`: Optional department/designation linkage
  - `is_system_role`: Protection flag for system roles

#### RoleModule Model
- **Purpose**: Links roles to modules (many-to-many relationship)
- **Key Fields**:
  - `role`: Foreign key to Role
  - `module_id`: Integer module ID
  - `module_name`: Human-readable module name

#### UserProfile Model
- **Purpose**: Extends Django User with role and module access
- **Key Fields**:
  - `user`: OneToOne with Django User
  - `role`: Foreign key to Role
  - `employee`: OneToOne with Employee (optional)
  - `access_modules`: JSONField storing list of module IDs
  - `assigned_date`: When role was assigned
  - `assigned_by`: User who assigned the role

#### Employee Model
- **Purpose**: HR employee records
- **Key Fields**:
  - `user`: OneToOne with Django User (optional)
  - `department`, `designation`, `branch`: Organizational structure

---

## Role Management

### Creating a Role

1. Navigate to **User Management > Roles & Permissions**
2. Click **Add Role**
3. Fill in:
   - Role name (required, unique)
   - Description (optional)
   - Permission flags (is_staff, is_active, is_superuser)
   - Department/Designation (optional)
   - **Module Access**: Select modules this role can access
4. Click **Create Role**

### Editing a Role

1. Navigate to role list or role detail page
2. Click **Edit** on the role
3. Modify fields as needed
4. **Important**: Changing modules will update all users with this role

### Deleting a Role

**Restrictions**:
- Cannot delete if role is assigned to any users
- Cannot delete system roles (`is_system_role=True`)

**Process**:
1. Navigate to role detail page
2. Click **Delete**
3. Provide deletion reason (logged for audit)
4. System validates no users are assigned
5. Role is deleted and logged in `RoleDeletionLog`

### Assigning Modules to Roles

Modules are assigned via checkboxes in the role form. Available modules:

1. Main Menu (ID: 1)
2. Inventory (ID: 2)
3. Stock (ID: 3)
4. Sales (ID: 4)
5. Staff (ID: 5)
6. Finance (ID: 6)
7. User Management (ID: 7)
8. Reports (ID: 8)
9. Settings (ID: 9)
10. Dashboard (ID: 10)
11. Batch Management (ID: 11)
12. Supplier Management (ID: 12)
13. Customer Management (ID: 13)
14. Expense Management (ID: 14)
15. Role Management (ID: 15)
16. Accounting (ID: 16)

---

## User Management

### Creating a User

**Location**: `app/views/user_views.py` - `user_create_view`

**Process**:
1. Navigate to **User Management > Users**
2. Click **Add User**
3. Fill in basic information:
   - Username (required, unique)
   - Email (required, unique)
   - First Name, Last Name
4. **Employee Linkage** (optional):
   - Select existing employee (without user account)
   - Create new employee inline
   - No employee linkage
5. **Role Assignment** (optional):
   - Select role from dropdown
6. Click **Create User**

**What Happens**:
- User account is created with auto-generated password
- Employee record is created/linked if specified
- UserProfile is created
- Role is assigned if selected
- **Email is sent** with default password and login instructions

### Editing a User

1. Navigate to user detail page
2. Click **Edit**
3. Modify fields:
   - Username, email, names
   - Active/Staff status
   - Role assignment
4. Click **Update User**

### Assigning Roles to Users

**Method 1**: During user creation/edit
- Select role in the form

**Method 2**: Via role assignment page
1. Navigate to user detail page
2. Click **Assign Role**
3. Select role from dropdown
4. Click **Assign Role**

**What Happens**:
- UserProfile.role is updated
- UserProfile.assigned_by is set to current user
- UserProfile.assigned_date is set
- Role permissions are applied to user
- User's access_modules are updated from role

### Deleting/Deactivating Users

**Options**:
1. **Deactivate** (Recommended):
   - User cannot log in
   - All data preserved
   - Can be reactivated later

2. **Delete Permanently**:
   - User and associated data removed
   - Cannot be undone

**Restrictions**:
- Cannot delete your own account
- System checks for critical module access (defensive)

---

## Permission Enforcement

### Decorator-Based Access Control

**Location**: `app/utils/decorators.py`

#### @require_module_access(module_id)

```python
from app.utils.decorators import require_module_access

@require_module_access(2)  # Requires Inventory module
def my_view(request):
    # Only users with Inventory module access can reach here
    ...
```

#### @require_url_access(url_name)

```python
from app.utils.decorators import require_url_access

@require_url_access('products_page')
def products_view(request):
    # Only users with access to products_page can reach here
    ...
```

### How It Works

1. **Superuser Check**: Superusers bypass all checks
2. **Authentication Check**: Unauthenticated users are redirected to login
3. **Module Access Check**: 
   - Retrieves user's `UserProfile.access_modules`
   - Checks if required module_id is in the list
   - Returns 404 if access denied

### Applying to Views

**Example**:
```python
from app.utils.decorators import require_module_access

@login_required
@require_module_access(2)  # Inventory module
def products_page(request):
    # View code
    ...
```

---

## Navigation Filtering

### How Sidebar Filtering Works

**Location**: `app/context_processors.py` - `app_menu()`

**Process**:
1. Context processor runs on every request
2. Gets user's `UserProfile.access_modules` (list of module IDs)
3. For each menu item:
   - Gets `url_name` from menu item
   - Looks up module ID in `MENU_MODULE_MAP`
   - Checks if user has access to that module
   - Filters out unauthorized items
4. Returns filtered menu to template

### Module Mapping

**Location**: `app/utils/module_mapping.py`

The `MENU_MODULE_MAP` dictionary maps URL names to module IDs:

```python
MENU_MODULE_MAP = {
    'products_page': 2,  # Inventory
    'sales_list': 4,     # Sales
    'roles_list_page': 15,  # Role Management
    # ... etc
}
```

### Menu Structure

Menu items in `app_menu()` context processor:
- Each item has `url_name` field
- Items are filtered based on user's module access
- Nested children are also filtered
- Empty parent items are removed

---

## Module System

### Module IDs

Modules are identified by integer IDs (1-16). The mapping is defined in:
- `app/models/human_resource.py` - `get_module_name_by_id()`
- `app/utils/module_mapping.py` - `MENU_MODULE_MAP`

### Adding a New Module

1. **Add to module mapping function**:
   ```python
   # In app/models/human_resource.py
   def get_module_name_by_id(module_id):
       module_map = {
           # ... existing modules
           17: 'New Module Name',
       }
   ```

2. **Add to MENU_MODULE_MAP**:
   ```python
   # In app/utils/module_mapping.py
   MENU_MODULE_MAP = {
       # ... existing mappings
       'new_url_name': 17,
   }
   ```

3. **Add to menu structure**:
   ```python
   # In app/context_processors.py - app_menu()
   {
       'label': 'New Module',
       'icon': 'ti ti-icon fs-16 me-2',
       'children': [
           {'label': 'New Feature', 'url_name': 'new_url_name'},
       ],
   }
   ```

4. **Apply decorator to views**:
   ```python
   @require_module_access(17)
   def new_view(request):
       ...
   ```

---

## Signals and Automation

### User Creation Signal

**Location**: `app/signals/user_signals.py`

**Trigger**: When `User` is created
**Action**: Creates `UserProfile` automatically

### Role Assignment Signal

**Location**: `app/signals/user_signals.py`

**Trigger**: When `UserProfile.role` is updated
**Action**: 
- Syncs `access_modules` from role
- Applies role permissions to user

### Employee-User Sync Signal

**Location**: `app/signals/user_signals.py`

**Trigger**: When `Employee` is saved
**Action**:
- Links employee to `UserProfile` if user exists
- Updates `UserProfile.department` from employee

### Role Update Signal

**Location**: `app/models/human_resource.py` - `Role.set_modules()`

**Trigger**: When role modules are updated
**Action**: 
- Updates all users with this role
- Refreshes their `access_modules`
- Applies updated permissions

---

## Usage Examples

### Example 1: Creating a Manager Role

```python
from app.models.human_resource import Role

# Create role
role = Role.objects.create(
    name='Department Manager',
    description='Manages department operations',
    is_staff=True,
    is_active=True,
    is_superuser=False
)

# Assign modules
role.set_modules([1, 2, 3, 4, 5, 8, 10])  # Main Menu, Inventory, Stock, Sales, Staff, Reports, Dashboard
```

### Example 2: Assigning Role to User

```python
from app.models.human_resource import UserProfile, Role
from django.contrib.auth.models import User

user = User.objects.get(username='john')
role = Role.objects.get(name='Department Manager')

# Get or create profile
profile, created = UserProfile.objects.get_or_create(user=user)

# Assign role
profile.role = role
profile.assigned_by = request.user  # Current admin
profile.save()

# Apply role
role.apply_to_user(user)
```

### Example 3: Checking Module Access

```python
from app.utils.module_mapping import user_has_module_access

if user_has_module_access(user, 2):  # Inventory module
    # User has access
    pass
```

### Example 4: Protecting a View

```python
from app.utils.decorators import require_module_access
from django.contrib.auth.decorators import login_required

@login_required
@require_module_access(2)  # Inventory module
def manage_products(request):
    # Only users with Inventory access can access
    ...
```

---

## Best Practices

1. **Role Design**:
   - Create roles based on job functions
   - Assign minimum required modules
   - Use descriptive names

2. **User Management**:
   - Always link employees to users when possible
   - Assign roles immediately after user creation
   - Use deactivation instead of deletion when possible

3. **Permission Enforcement**:
   - Apply `@require_module_access` to all views
   - Test with different role assignments
   - Document module requirements

4. **Navigation**:
   - Keep menu structure organized
   - Use consistent URL naming
   - Update module mapping when adding new views

5. **Security**:
   - Never bypass permission checks for superusers
   - Always validate on both frontend and backend
   - Log role assignments and changes

---

## Troubleshooting

### User Cannot See Menu Items

**Check**:
1. User has a role assigned
2. Role has modules assigned
3. UserProfile.access_modules is populated
4. URL is in MENU_MODULE_MAP

**Solution**:
```python
# Refresh user's modules
profile = user.profile
profile.update_modules_from_role()
```

### Permission Denied Errors

**Check**:
1. View has `@require_module_access` decorator
2. User's role includes required module
3. UserProfile.access_modules is up to date

**Solution**:
```python
# Reapply role to user
role.apply_to_user(user)
```

### Email Not Sending

**Check**:
1. Django email settings configured
2. DEFAULT_FROM_EMAIL is set
3. Email backend is working

**Solution**: Check `settings.py` for email configuration

---

## API Reference

### Role Methods

- `role.get_module_ids()`: Returns list of module IDs
- `role.get_module_names()`: Returns list of module names
- `role.set_modules(module_ids)`: Sets modules for role
- `role.apply_to_user(user)`: Applies role to user
- `role.update_all_users()`: Updates all users with this role

### UserProfile Methods

- `profile.update_modules_from_role()`: Syncs modules from role

### Utility Functions

- `get_module_id_for_url(url_name)`: Get module ID for URL
- `user_has_module_access(user, module_id)`: Check module access
- `user_has_url_access(user, url_name)`: Check URL access

---

## Conclusion

This role management system provides comprehensive access control through module-based permissions. It integrates seamlessly with the existing Django User and Employee models, providing a flexible and secure way to manage user access across the enterprise system.

For questions or issues, refer to the codebase or contact the development team.


