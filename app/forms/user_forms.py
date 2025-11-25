from django import forms
from django.forms import ModelForm, inlineformset_factory
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from app.models.human_resource import Employee, UserProfile, Role, Department, Designation
from app.forms.human_resource_forms import EmployeeForm

class UserCreateForm(forms.Form):
    """Form for creating a new user with optional employee creation"""
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email'})
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'})
    )
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Assign one or more roles to this user (optional)"
    )
    
    # Employee selection/creation
    employee_option = forms.ChoiceField(
        choices=[
            ('existing', 'Select Existing Employee'),
            ('new', 'Create New Employee'),
            ('none', 'No Employee Link')
        ],
        initial='none',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text="Choose how to handle employee linkage"
    )
    existing_employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(user__isnull=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select an employee without a user account"
    )
    
    # New employee fields (if creating new employee)
    create_employee = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Create a new employee record for this user"
    )
    gender = forms.ChoiceField(
        choices=[('M', 'Male'), ('F', 'Female')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    contact = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'})
    )
    branch = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    designation = forms.ModelChoiceField(
        queryset=Designation.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_joined = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.models.organization import Branch
        self.fields['branch'].queryset = Branch.objects.all()
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        employee_option = cleaned_data.get('employee_option')
        
        if employee_option == 'existing':
            if not cleaned_data.get('existing_employee'):
                raise forms.ValidationError("Please select an existing employee.")
        elif employee_option == 'new':
            # Validate required fields for new employee
            if not cleaned_data.get('gender'):
                raise forms.ValidationError("Gender is required when creating a new employee.")
            if not cleaned_data.get('contact'):
                raise forms.ValidationError("Contact number is required when creating a new employee.")
            if not cleaned_data.get('branch'):
                raise forms.ValidationError("Branch is required when creating a new employee.")
            if not cleaned_data.get('department'):
                raise forms.ValidationError("Department is required when creating a new employee.")
            if not cleaned_data.get('date_joined'):
                raise forms.ValidationError("Date joined is required when creating a new employee.")
        
        return cleaned_data

class UserEditForm(forms.ModelForm):
    """Form for editing an existing user (RBAC 2.0: supports multiple roles)"""
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Assign one or more roles to this user"
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial roles if user has a profile (RBAC 2.0)
        if self.instance and self.instance.pk:
            try:
                profile = self.instance.profile
                if profile.roles.exists():
                    self.fields['roles'].initial = list(profile.roles.values_list('id', flat=True))
            except UserProfile.DoesNotExist:
                pass
    
    def save(self, commit=True):
        user = super().save(commit=commit)
        # Note: Role assignment is handled in the view
        return user

class RoleAssignmentForm(forms.Form):
    """Form for assigning roles to a user (RBAC 2.0: supports multiple roles)"""
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=True,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Select one or more roles to assign to this user"
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            try:
                profile = self.user.profile
                if profile.roles.exists():
                    self.fields['roles'].initial = list(profile.roles.values_list('id', flat=True))
            except UserProfile.DoesNotExist:
                pass

