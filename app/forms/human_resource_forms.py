
from django.forms import ModelForm
from app.models.human_resource import *

class EmployeeForm(ModelForm):
    class Meta:
        model = Employee
        fields = ('__all__')

class DepartmentForm(ModelForm):
    class Meta:
        model = Department
        fields = ('__all__')

class DesignationForm(ModelForm):
    class Meta:
        model = Designation
        fields = ('__all__')