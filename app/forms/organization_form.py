from django.forms import ModelForm
from app.models.organization import *

class BranchForm(ModelForm):
    
    class Meta:
        model = Branch
        fields = ("__all__")
