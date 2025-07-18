# Generated by Django 5.2.1 on 2025-07-18 07:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0015_merge_20250713_1547'),
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Department',
                'verbose_name_plural': 'Departments',
            },
        ),
        migrations.RemoveField(
            model_name='sales',
            name='branch',
        ),
        migrations.AlterField(
            model_name='stockmovement',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_movements', to='app.product'),
        ),
        migrations.CreateModel(
            name='Designation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='designations', to='app.department')),
            ],
            options={
                'verbose_name': 'Designation',
                'verbose_name_plural': 'Designations',
                'unique_together': {('title', 'department')},
            },
        ),
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('gender', models.CharField(choices=[('M', 'Male'), ('F', 'Female')], max_length=10)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('contact', models.CharField(max_length=20)),
                ('date_joined', models.DateField()),
                ('is_active', models.BooleanField(default=True)),
                ('address', models.TextField(blank=True, null=True)),
                ('photo', models.ImageField(blank=True, null=True, upload_to='employee_photos/')),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='employees', to='app.branch')),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='employees', to='app.department')),
                ('designation', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employees', to='app.designation')),
            ],
            options={
                'verbose_name': 'Employee',
                'verbose_name_plural': 'Employees',
                'unique_together': {('email', 'first_name', 'last_name', 'department')},
            },
        ),
    ]
