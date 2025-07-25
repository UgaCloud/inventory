# Generated by Django 5.2.1 on 2025-07-08 04:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0010_alter_stockmovement_transaction_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='stocktransfer',
            name='branch',
        ),
        migrations.RemoveField(
            model_name='stocktransfer',
            name='from_store',
        ),
        migrations.RemoveField(
            model_name='stocktransfer',
            name='product',
        ),
        migrations.RemoveField(
            model_name='stocktransfer',
            name='quantity',
        ),
        migrations.RemoveField(
            model_name='stocktransfer',
            name='to_store',
        ),
        migrations.AddField(
            model_name='stocktransfer',
            name='completed_by',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='stocktransfer',
            name='note',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='stockmovement',
            name='transaction_type',
            field=models.CharField(choices=[('Initial Stock', 'Initial Stock'), ('Stocked', 'Stocked'), ('Sold', 'Sold'), ('In', 'In'), ('Out', 'Out'), ('Transfered', 'Transfered'), ('Returned', 'Returned'), ('Expired', 'Expired'), ('Damaged', 'Damaged'), ('Stolen', 'Stolen'), ('Removed', 'Removed')], max_length=50),
        ),
        migrations.AlterUniqueTogether(
            name='purchaseorderitem',
            unique_together={('order', 'product', 'unit')},
        ),
        migrations.AlterUniqueTogether(
            name='salesitem',
            unique_together={('order', 'product', 'unit')},
        ),
        migrations.CreateModel(
            name='TransferRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('requested_by', models.CharField(max_length=100)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('fulfilled', 'Fulfilled')], default='pending', max_length=20)),
                ('request_date', models.DateTimeField(auto_now_add=True)),
                ('approved_by', models.CharField(blank=True, max_length=100, null=True)),
                ('approved_date', models.DateTimeField(blank=True, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('from_store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transfer_requests_out', to='app.storelocation')),
                ('to_store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transfer_requests_in', to='app.storelocation')),
            ],
        ),
        migrations.AddField(
            model_name='stocktransfer',
            name='transfer_request',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='stock_transfers', to='app.transferrequest'),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='StockTransferItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product')),
                ('stock_transfer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='app.stocktransfer')),
            ],
            options={
                'unique_together': {('stock_transfer', 'product')},
            },
        ),
    ]
