from django.forms import ModelForm
from app.models.organization import *

class BranchForm(ModelForm):
    
    class Meta:
        model = Branch
        fields = ("__all__")

class OrganizationSettingForm(ModelForm):
    class Meta:
        model = OrganizationSetting
        fields = ("country","city", "address", "postal","website", "organization_name", "organization_motto", "mobile",
                  "office_phone_number1", "office_phone_number2", "organization_logo", "app_name", "currency")