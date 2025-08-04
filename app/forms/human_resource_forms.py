from django import forms
from django.forms import ModelForm
from app.models.human_resource import *
from django.contrib.auth.models import User

class EmployeeForm(forms.ModelForm):
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=False, help_text="Link to a Django user account (optional)")
    class Meta:
        model = Employee
        fields = '__all__'

class DepartmentForm(ModelForm):
    class Meta:
        model = Department
        fields = ('__all__')

class DesignationForm(ModelForm):
    class Meta:
        model = Designation
        fields = ('__all__')