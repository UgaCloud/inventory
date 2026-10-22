from django.db import models
from django.urls import reverse

from AbstractModels.singleton import SingletonModel
from app.constants import *
from app.managers import TenantManager


class Currency(models.Model):
    code = models.CharField(max_length=10, unique=True, default="UGX")
    desc = models.CharField(max_length=20, default="Ugandan Shillings")
    cost = models.CharField(max_length=20, default="1")

    def __str__(self):
        return self.code


class OrganizationSetting(SingletonModel):
    business = models.ForeignKey(
        "app.Business", on_delete=models.CASCADE, null=True, blank=True,
        related_name="organization_settings",
        help_text="Tenant this settings row belongs to (NULL = platform-wide legacy row)",
    )
    country = models.CharField(max_length=40, choices=COUNTRIES, default="Uganda")
    city = models.CharField(max_length=40, default="Kampala")
    address = models.CharField(max_length=50, default="", blank=True)
    postal = models.CharField(max_length=50, default="", blank=True)
    website = models.CharField(max_length=50, default="", blank=True)
    organization_name = models.CharField(max_length=50, default="")
    organization_motto = models.CharField(max_length=150, blank=True, null=True)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    office_phone_number1 = models.CharField(max_length=20, blank=True, null=True)
    office_phone_number2 = models.CharField(max_length=40, blank=True, null=True)
    organization_logo = models.ImageField(
        upload_to="logo",
        height_field=None,
        width_field=None,
        max_length=None,
        blank=True,
        null=True,
    )
    app_name = models.CharField(max_length=20, default="Inventory")
    currency = models.CharField(max_length=50, choices=CURRENCY_CHOICES, default="UGX")

    # Fields a business inherits from the platform wide row the first time
    # its own company profile is created.
    COPYABLE_FIELDS = (
        'country', 'city', 'address', 'postal', 'website',
        'organization_name', 'organization_motto', 'mobile',
        'office_phone_number1', 'office_phone_number2', 'app_name', 'currency',
    )

    def save(self, *args, **kwargs):
        # The row without a business is the platform wide singleton and keeps
        # its fixed id. Every business owns a separate copy of the company
        # profile, which therefore must not be forced onto that id.
        if self.business_id is None:
            self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)

    @classmethod
    def load_for(cls, business):
        """
        The company profile of a business.

        Every tenant owns its own row. The first time a business asks for
        its profile, the platform wide row is copied so the company keeps
        the details that were configured before the tenants were split.
        """
        if business is None:
            return cls.load()

        row = cls.objects.filter(business=business).first()
        if row is not None:
            return row

        legacy = cls.objects.filter(business__isnull=True).first()
        if legacy is None:
            legacy = cls()
            legacy._audit_skip = True
            legacy.save()

        row = cls(business=business)
        for name in cls.COPYABLE_FIELDS:
            setattr(row, name, getattr(legacy, name))
        row._audit_skip = True
        row.save()
        return row


class Branch(models.Model):

    objects = TenantManager()

    business = models.ForeignKey(
        "app.Business", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="branches",
    )
    name = models.CharField(max_length=100)
    location = models.TextField(blank=True)
    contact_person = models.CharField(max_length=150)
    contact = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Branch"
        verbose_name_plural = "Branches"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("Branch_detail", kwargs={"pk": self.pk})
