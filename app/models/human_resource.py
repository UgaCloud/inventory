from django.db import models
from django.contrib.auth.models import User
from app.constants import GENDERS

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
