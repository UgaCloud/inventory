from django.db import models
from django.urls import reverse
from AbstractModels.singleton import SingletonModel
from app.constants import *

class Currency(models.Model):
    code = models.CharField(max_length=10, unique=True, default="UGX")
    desc = models.CharField(max_length=20, default="Ugandan Shillings")
    cost = models.CharField(max_length=20, default="1")

    def __str__(self):
        return self.code


class OrganizationSetting(SingletonModel):
    
    country = models.CharField(max_length=40, choices=COUNTRIES, default="Uganda")
    city = models.CharField(max_length=40, default="Kampala")
    address = models.CharField(max_length=50, default="None")
    postal = models.CharField(max_length=50, default="None")
    website = models.CharField(max_length=50, default="None")
    organization_name = models.CharField(max_length=50, default="None")
    organization_motto = models.CharField(max_length=150, blank=True, null=True)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    office_phone_number1 = models.CharField(max_length=20, blank=True, null=True)
    office_phone_number2 = models.CharField(max_length=40, blank=True, null=True)
    organization_logo = models.ImageField(upload_to="logo", height_field=None, width_field=None, max_length=None)
    app_name = models.CharField(max_length=20, default="Inventory")
    
class Branch(models.Model):

    name = models.CharField(max_length=100)
    location = models.TextField(blank=True)
    contact_person = models.CharField(max_length=150)
    contact = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = ("Branch")
        verbose_name_plural = ("Branches")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("Branch_detail", kwargs={"pk": self.pk})
  
