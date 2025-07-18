# Generated by Django 5.2.1 on 2025-07-06 07:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0010_alter_stockmovement_transaction_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockmovement',
            name='transaction_type',
            field=models.CharField(choices=[('Initial Stock', 'Initial Stock'), ('Stocked', 'Stocked'), ('Sold', 'Sold'), ('In', 'In'), ('Out', 'Out'), ('Transfered', 'Transfered'), ('Returned', 'Returned'), ('Expired', 'Expired'), ('Damaged', 'Damaged'), ('Stolen', 'Stolen'), ('Removed', 'Removed')], max_length=50),
        ),
    ]
