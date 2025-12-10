from django.db import models
from django.contrib.auth.models import User, Group
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum
import datetime

from app.constants import GENDERS

# Department and Designation models (your existing code)
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return self.name

    @property
    def employee_count(self):
        return self.employees.count()

class Designation(models.Model):
    title = models.CharField(max_length=100, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='designations')
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Designation"
        verbose_name_plural = "Designations"
        unique_together = ("title", "department")

    def __str__(self):
        return f"{self.title} ({self.department.name})"

    @property
    def employee_count(self):
        return self.employees.count()

# Employee model (your existing code)
class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_profile')
    gender = models.CharField(max_length=10, choices=GENDERS)
    contact = models.CharField(max_length=20)
    branch = models.ForeignKey('app.Branch', on_delete=models.RESTRICT, related_name='employees')
    department = models.ForeignKey(Department, on_delete=models.RESTRICT, related_name='employees')
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, related_name='employees')
    date_joined = models.DateField()
    is_active = models.BooleanField(default=True)
    address = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True)

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        unique_together = ("user", "department")

    def __str__(self):
        if self.user:
            return f"{self.user.get_full_name()}"
        return f"Employee {self.pk}"

    @property
    def email(self):
        return self.user.email if self.user else None

    @property
    def first_name(self):
        return self.user.first_name if self.user else None

    @property
    def last_name(self):
        return self.user.last_name if self.user else None

# Role System Models (Integrated with your Employee system)
class Role(models.Model):
    """Application Role backed by Django Group for permissions."""
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, default='')
    
    # Django permission fields
    is_staff = models.BooleanField(
        default=False, 
        help_text="Users with this role can access the admin site"
    )
    is_active = models.BooleanField(
        default=True, 
        help_text="Users with this role will be active by default"
    )
    is_superuser = models.BooleanField(
        default=False, 
        help_text="Users with this role will have all permissions"
    )
    
    # Link to Department/Designation for role-based access control
    department = models.ForeignKey(
        Department, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='roles',
        help_text="Optional: Department this role is associated with"
    )
    designation = models.ForeignKey(
        Designation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roles',
        help_text="Optional: Designation this role is associated with"
    )
    
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='role', null=True, blank=True)
    is_system_role = models.BooleanField(default=False, help_text="System roles cannot be deleted")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure backing Group exists and is kept in sync
        if not self.group:
            grp, _ = Group.objects.get_or_create(name=self.name)
            self.group = grp
        else:
            if self.group.name != self.name:
                self.group.name = self.name
                self.group.save(update_fields=['name'])
        
        # Sync Django permissions to the group if needed
        self._sync_permissions_to_group()
        
        # Save first to get PK
        super().save(*args, **kwargs)
        
        # SECTION 1: Superuser auto-module assignment
        # If is_superuser=True and role has PK, auto-assign ALL modules (1-16)
        if self.is_superuser and self.pk:
            # Check if we need to assign all modules
            current_modules = set(self.get_module_ids())
            all_modules = set(range(1, 17))
            
            # Only update if not all modules are already assigned (avoid recursion)
            if current_modules != all_modules:
                # Use set_modules which will trigger update_all_users
                self.set_modules(list(all_modules))
                print(f"Auto-assigned all modules (1-16) to superuser role: {self.name}")

    def _sync_permissions_to_group(self):
        """Sync Django permissions to the associated group if this role has superuser status"""
        if self.is_superuser and self.group:
            # For superuser roles, we might want to add all permissions
            # or handle this differently based on your needs
            pass

    def get_module_ids(self):
        """Get list of module IDs for this role"""
        return list(self.modules.values_list('module_id', flat=True))

    def get_module_names(self):
        """Get list of module names for this role"""
        return list(self.modules.values_list('module_name', flat=True))

    def get_dashboards(self):
        """
        Get list of dashboard names assigned to this role based on its modules.
        Returns empty list if role has no modules.
        """
        from app.utils.dashboard_assignment import get_dashboards_for_modules
        module_ids = self.get_module_ids()
        if not module_ids:
            return []
        return get_dashboards_for_modules(module_ids)

    def get_dashboard_templates(self):
        """
        Get list of dashboard template paths assigned to this role based on its modules.
        Returns empty list if role has no modules.
        """
        from app.utils.dashboard_assignment import get_dashboard_templates_for_modules
        module_ids = self.get_module_ids()
        if not module_ids:
            return []
        return get_dashboard_templates_for_modules(module_ids)

    def get_dashboard_info(self):
        """
        Get list of dictionaries with dashboard information (name and template path).
        Returns empty list if role has no modules.
        
        Returns:
            List of dicts with 'name' and 'template' keys
        """
        from app.utils.dashboard_assignment import get_dashboard_info_for_modules
        module_ids = self.get_module_ids()
        if not module_ids:
            return []
        return get_dashboard_info_for_modules(module_ids)

    @property
    def dashboard_count(self):
        """Number of dashboards assigned to this role"""
        return len(self.get_dashboards())

    def add_module(self, module_id, module_name):
        """Add a module to this role"""
        RoleModule.objects.get_or_create(
            role=self,
            module_id=module_id,
            defaults={'module_name': module_name}
        )

    def remove_module(self, module_id):
        """Remove a module from this role"""
        self.modules.filter(module_id=module_id).delete()

    def set_modules(self, module_data):
        """
        Set modules for this role
        module_data: list of module IDs
        """
        
        # Clear existing modules
        deleted_count = self.modules.all().delete()[0]
        
        # Add new modules
        for module_id in module_data:
            module_name = get_module_name_by_id(module_id)
            RoleModule.objects.create(
                role=self,
                module_id=module_id,
                module_name=module_name
            )
        
        # Update all users with this role
        self.update_all_users()

    def update_all_users(self):
        """Update all users with this role to sync modules and permissions (RBAC 2.0)"""
        user_profiles = self.assigned_profiles.all()
        
        updated_count = 0
        for user_profile in user_profiles:
            try:
                # Update modules from all roles (RBAC 2.0)
                user_profile.update_modules_from_roles()
                
                # Update Django user permissions (use highest privilege from all roles)
                try:
                    user = user_profile.user
                    # Check all roles for highest privileges
                    has_staff = user_profile.roles.filter(is_staff=True).exists()
                    has_superuser = user_profile.roles.filter(is_superuser=True).exists()
                    is_active = user_profile.roles.filter(is_active=True).exists()
                    
                    user.is_staff = has_staff or user.is_staff
                    user.is_active = is_active if is_active else user.is_active
                    user.is_superuser = has_superuser or user.is_superuser
                    user.save(update_fields=['is_staff', 'is_active', 'is_superuser'])
                    updated_count += 1
                    print(f"Updated permissions for {user.username}")
                except Exception as e:
                    print(f"Could not update permissions for {user_profile.user.username}: {e}")
            except Exception as e:
                print(f"Error updating user {user_profile.user.username}: {e}")
        

    def get_permissions_dict(self):
        """Return Django permissions as a dictionary"""
        return {
            'is_staff': self.is_staff,
            'is_active': self.is_active,
            'is_superuser': self.is_superuser
        }

    def apply_to_user(self, user):
        """Apply this role's permissions and modules to a user (RBAC 2.0: adds to roles M2M)"""
        # Update or create UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # RBAC 2.0: Add role to M2M (don't replace)
        if self not in profile.roles.all():
            profile.roles.add(self)
        
        # Update modules from all roles
        profile.update_modules_from_roles()
        
        # Update Django user permissions (use highest privilege from all roles)
        has_staff = profile.roles.filter(is_staff=True).exists()
        has_superuser = profile.roles.filter(is_superuser=True).exists()
        is_active = profile.roles.filter(is_active=True).exists()
        
        user.is_staff = has_staff or user.is_staff
        user.is_active = is_active if is_active else user.is_active
        user.is_superuser = has_superuser or user.is_superuser
        user.save(update_fields=['is_staff', 'is_active', 'is_superuser'])
        
        # Assign to group (add, don't replace)
        if self.group:
            user.groups.add(self.group)
        
        return profile

    @property
    def user_count(self):
        """Number of users with this role (RBAC 2.0: counts M2M relationships)"""
        return self.assigned_profiles.count()

    @property
    def module_count(self):
        """Number of modules assigned to this role"""
        return self.modules.count()

    @property
    def department_name(self):
        """Get department name for display"""
        return self.department.name if self.department else "All Departments"

    @property
    def designation_title(self):
        """Get designation title for display"""
        return self.designation.title if self.designation else "All Designations"


class RoleModule(models.Model):
    """
    Connects a Role with the modules it has access to.
    """
    role = models.ForeignKey('Role', on_delete=models.CASCADE, related_name='modules')
    module_id = models.PositiveIntegerField()
    module_name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('role', 'module_id')
        ordering = ['module_id']
        verbose_name = "Role Module"
        verbose_name_plural = "Role Modules"

    def __str__(self):
        return f"{self.role.name} → {self.module_name}"


class RoleDeletionLog(models.Model):
    role = models.ForeignKey(
        'Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deletion_logs'
    )
    role_name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)
    is_system_role = models.BooleanField(default=False)
    department_name = models.CharField(max_length=100, blank=True, default='')
    designation_title = models.CharField(max_length=100, blank=True, default='')
    module_count = models.IntegerField(default=0)
    user_count = models.IntegerField(default=0)
    reason = models.TextField()
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='role_deletions'
    )
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-deleted_at']
        verbose_name = "Role Deletion Log"
        verbose_name_plural = "Role Deletion Logs"

    def __str__(self):
        return f"Deleted Role {self.role_name}"

    @classmethod
    def log_from_role(cls, role, reason, user=None):
        """Create deletion log from role instance"""
        return cls.objects.create(
            role=role,
            role_name=role.name,
            description=role.description,
            is_staff=role.is_staff,
            is_active=role.is_active,
            is_superuser=role.is_superuser,
            is_system_role=role.is_system_role,
            department_name=role.department.name if role.department else '',
            designation_title=role.designation.title if role.designation else '',
            module_count=role.modules.count(),
            user_count=role.assigned_profiles.count(),
            reason=reason,
            deleted_by=user
        )


# Updated UserProfile model that integrates with both Employee and Role systems (RBAC 2.0)
class UserProfile(models.Model):
    """
    Extends the Django User model with role, department, and module access information.
    Integrates with Employee model for comprehensive user management.
    RBAC 2.0: Supports multiple roles per user with composite permissions.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # RBAC 2.0: Multiple roles per user (ManyToMany)
    roles = models.ManyToManyField(
        'Role', 
        related_name='assigned_profiles', 
        blank=True,
        help_text="Multiple roles assigned to this user"
    )
    
    # Legacy single role field (kept for migration compatibility, will be removed)
    role = models.ForeignKey(
        'Role', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='legacy_user_profiles',
        help_text="DEPRECATED: Use roles M2M field instead"
    )
    
    assigned_date = models.DateTimeField(auto_now_add=True, help_text="Date when role was assigned")
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_profiles',
        help_text="User who assigned this role"
    )
    
    # Link to Employee record (optional - for users who are also employees)
    employee = models.OneToOneField(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='user_profile',
        help_text="Linked employee record (if user is an employee)"
    )
    
    # Additional profile fields
    department = models.CharField(max_length=255, blank=True, null=True)
    access_modules = models.JSONField(default=list, blank=True, help_text="List of module IDs the user has access to")
    password_created_by = models.CharField(max_length=10, choices=[('admin','Admin'),('user','User')], default='admin')
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated', '-created']
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        role_count = self.roles.count()
        role_names = ", ".join([r.name for r in self.roles.all()[:2]])
        if role_count > 2:
            role_names += f" (+{role_count - 2} more)"
        role_info = role_names if role_names else 'No Roles'
        employee_info = f" - {self.employee}" if self.employee else ""
        return f"{self.user.username} - {role_info}{employee_info}"

    def save(self, *args, **kwargs):
        # Auto-populate department from employee if available
        if self.employee and not self.department:
            self.department = self.employee.department.name
        
        super().save(*args, **kwargs)
        
        # Update access_modules from effective_modules (for backward compatibility)
        effective = self.effective_modules
        if self.access_modules != effective:
            UserProfile.objects.filter(pk=self.pk).update(access_modules=effective)
            self.access_modules = effective

    @property
    def effective_modules(self):
        """
        RBAC 2.0: Compute effective modules from all assigned roles.
        Returns union of all modules from all roles.
        If any role is superuser, returns ALL modules (1-16).
        """
        if not self.pk:
            return []
        
        # Check if any role is superuser
        if self.roles.filter(is_superuser=True).exists():
            return list(range(1, 17))  # All modules
        
        # Union of all modules from all roles
        all_module_ids = set()
        for role in self.roles.all():
            module_ids = role.get_module_ids()
            all_module_ids.update(module_ids)
        
        return sorted(list(all_module_ids))

    def update_modules_from_roles(self):
        """Update user's access modules from all assigned roles (RBAC 2.0)"""
        if self.pk:
            try:
                effective = self.effective_modules
                # Update DB
                UserProfile.objects.filter(pk=self.pk).update(access_modules=effective)
                # Update in-memory object
                self.access_modules = effective
                print(f"Updated modules for {self.user.username}: {effective}")
            except Exception as e:
                print(f"Error updating modules for {self.user.username}: {e}")

    def update_modules_from_role(self):
        """Legacy method - redirects to update_modules_from_roles"""
        self.update_modules_from_roles()

    @property
    def full_name(self):
        """Get user's full name"""
        if self.employee and self.employee.user:
            return self.employee.user.get_full_name()
        return self.user.get_full_name()

    @property
    def email(self):
        """Get user's email"""
        if self.employee and self.employee.user:
            return self.employee.user.email
        return self.user.email

    @property
    def is_employee(self):
        """Check if user has an associated employee record"""
        return self.employee is not None


# Helper functions
def get_module_name_by_id(module_id):
    """Helper function to get module name by ID"""
    module_map = {
        1: 'Main Menu',
        2: 'Inventory',
        3: 'Stock',
        4: 'Sales',
        5: 'Staff',
        6: 'Finance',
        7: 'User Management',
        8: 'Reports',
        9: 'Settings',
        10: 'Dashboard',
        11: 'Batch Management',
        12: 'Supplier Management',
        13: 'Customer Management',
        14: 'Expense Management',
        15: 'Role Management',
        16: 'Accounting',
    }
    return module_map.get(module_id, f'Module {module_id}')


def generate_role_code():
    """Generate unique role code"""
    today = datetime.datetime.today()
    base_id = f"ROL-{today.year}-{today.month:02d}-{today.day:02d}"
    
    counter = 1
    new_id = f"{base_id}-{counter}"

    # Increment counter until a unique ID is found
    while Role.objects.filter(name=new_id).exists():
        counter += 1
        new_id = f"{base_id}-{counter}"
        
    return new_id


# System Role Initialization Function
def initialize_system_roles():
    """Initialize essential system roles"""
    system_roles = [
        {
            'name': 'System Administrator',
            'description': 'Full system access with all permissions',
            'is_staff': True,
            'is_active': True,
            'is_superuser': True,
            'is_system_role': True,
            'modules': list(range(1, 17))  # All modules
        },
        {
            'name': 'Manager',
            'description': 'Department manager with limited administrative access',
            'is_staff': True,
            'is_active': True,
            'is_superuser': False,
            'is_system_role': False,
            'modules': [1, 2, 3, 4, 5, 6, 8, 10, 11, 12, 13, 14]  # Most modules except user/role management
        },
        {
            'name': 'Staff',
            'description': 'Regular staff member with basic access',
            'is_staff': False,
            'is_active': True,
            'is_superuser': False,
            'is_system_role': False,
            'modules': [1, 2, 3, 4, 10]  # Basic operational modules
        },
        {
            'name': 'View Only',
            'description': 'Read-only access to reports and dashboards',
            'is_staff': False,
            'is_active': True,
            'is_superuser': False,
            'is_system_role': False,
            'modules': [1, 8, 10]  # Only viewing modules
        }
    ]
    
    created_count = 0
    for role_data in system_roles:
        role, created = Role.objects.get_or_create(
            name=role_data['name'],
            defaults={
                'description': role_data['description'],
                'is_staff': role_data['is_staff'],
                'is_active': role_data['is_active'],
                'is_superuser': role_data['is_superuser'],
                'is_system_role': role_data['is_system_role']
            }
        )
        if created:
            role.set_modules(role_data['modules'])
            created_count += 1
            print(f"Created system role: {role.name}")
    
    print(f"System role initialization complete! Created {created_count} roles")
    return created_count






























