from django.db import models
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
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDERS)
    email = models.EmailField(unique=True)
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
        unique_together = ("email", "first_name", "last_name", "department")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
