from django import forms
from django.forms import ModelForm
from app.models.human_resource import Role, RoleModule
from app.models.human_resource import get_module_name_by_id

# Module choices based on the get_module_name_by_id function
MODULE_CHOICES = [
    (1, 'Main Menu'),
    (2, 'Inventory'),
    (3, 'Stock'),
    (4, 'Sales'),
    (5, 'Staff'),
    (6, 'Finance'),
    (7, 'User Management'),
    (8, 'Reports'),
    (9, 'Settings'),
    (10, 'Dashboard'),
    (11, 'Batch Management'),
    (12, 'Supplier Management'),
    (13, 'Customer Management'),
    (14, 'Expense Management'),
    (15, 'Role Management'),
    (16, 'Accounting'),
]

# Module ID for Admin Dashboard access
ADMIN_DASHBOARD_MODULE_ID = 10

class RoleCreateForm(ModelForm):
    """Form for creating a new role"""
    modules = forms.MultipleChoiceField(
        choices=MODULE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select modules this role can access"
    )
    
    class Meta:
        model = Role
        fields = ['name', 'description', 'is_staff', 'is_active', 'is_superuser', 'department', 'designation']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter role name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter role description'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_superuser': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'designation': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Set initial modules if editing
        if self.instance and self.instance.pk:
            module_ids = list(self.instance.modules.values_list('module_id', flat=True))
            self.fields['modules'].initial = [str(mid) for mid in module_ids]
        # Non-superusers cannot assign the Dashboard module (Admin Dashboard)
        if self.current_user and not self.current_user.is_superuser:
            self.fields['modules'].choices = [
                c for c in MODULE_CHOICES if c[0] != ADMIN_DASHBOARD_MODULE_ID
            ]
    
    def save(self, commit=True):
        role = super().save(commit=commit)
        if commit:
            # Get selected module IDs
            module_ids = [int(mid) for mid in self.cleaned_data.get('modules', [])]
            # Non-superusers cannot assign the Dashboard module
            if self.current_user and not self.current_user.is_superuser:
                module_ids = [m for m in module_ids if m != ADMIN_DASHBOARD_MODULE_ID]
                # Preserve existing Dashboard access when editing
                if self.instance and self.instance.pk:
                    has_dashboard = self.instance.modules.filter(
                        module_id=ADMIN_DASHBOARD_MODULE_ID
                    ).exists()
                    if has_dashboard and ADMIN_DASHBOARD_MODULE_ID not in module_ids:
                        module_ids.append(ADMIN_DASHBOARD_MODULE_ID)
            # Set modules for the role
            role.set_modules(module_ids)
        return role

class RoleEditForm(RoleCreateForm):
    """Form for editing an existing role"""
    pass

class RoleDeleteForm(forms.Form):
    """Form for deleting a role with reason"""
    reason = forms.CharField(
        max_length=500,
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter reason for deletion...'
        }),
        help_text="Please provide a reason for deleting this role"
    )
    
    def __init__(self, *args, **kwargs):
        self.role = kwargs.pop('role', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        if self.role:
            # Check if role has users assigned (RBAC 2.0: check M2M)
            user_count = self.role.assigned_profiles.count()
            if user_count > 0:
                raise forms.ValidationError(
                    f"Cannot delete role '{self.role.name}'. It is assigned to {user_count} user(s). "
                    "Please reassign or remove users before deleting this role."
                )
            # Check if it's a system role
            if self.role.is_system_role:
                raise forms.ValidationError(
                    f"Cannot delete system role '{self.role.name}'. System roles are protected."
                )
        return cleaned_data

