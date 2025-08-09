from django import forms
from django.forms import ModelForm
from app.models.human_resource import *
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string

class EmployeeForm(forms.ModelForm):
    # Add user fields for creation
    first_name = forms.CharField(max_length=30, required=True, label="First Name")
    last_name = forms.CharField(max_length=30, required=True, label="Last Name")
    email = forms.EmailField(required=True, label="Email")

    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        help_text="Link to a user account (optional)"
    )

    class Meta:
        model = Employee
        exclude = ('first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing, prepopulate user fields
        if self.instance and self.instance.pk and self.instance.user:
            self.fields['user'].disabled = True
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
        elif self.instance and self.instance.pk:
            self.fields['user'].disabled = False

    def save(self, commit=True):
        user = self.cleaned_data.get('user')
        first_name = self.cleaned_data.get('first_name')
        last_name = self.cleaned_data.get('last_name')
        email = self.cleaned_data.get('email')
        if not user:
            # Create a new user if not selected
            username = self.generate_unique_username(first_name, last_name)
            password = 'user_123' # Default password, should be changed later
            user = get_user_model().objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password
            )
        else:
            # Update user details if changed
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.save()
        self.instance.user = user
        return super().save(commit=commit)

    def generate_unique_username(self, first_name, last_name):
        base = (first_name[0] + last_name).lower()
        username = base
        UserModel = get_user_model()
        i = 1
        while UserModel.objects.filter(username=username).exists():
            username = f"{base}{i}"
            i += 1
        return username

class DepartmentForm(ModelForm):
    class Meta:
        model = Department
        fields = ('__all__')

class DesignationForm(ModelForm):
    class Meta:
        model = Designation
        fields = ('__all__')