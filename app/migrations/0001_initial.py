# Generated by Django 4.2.21 on 2025-05-29 09:03

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(default='UGX', max_length=10, unique=True)),
                ('desc', models.CharField(default='Ugandan Shillings', max_length=20)),
                ('cost', models.CharField(default='1', max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(max_length=20)),
                ('address', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='OrganizationSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('country', models.CharField(choices=[('UG', 'Uganda'), ('KE', 'Kenya'), ('TZ', 'Tanzania'), ('RD', 'Rwanda'), ('BD', 'Burundi'), ('SD', 'South Sudan')], default='Uganda', max_length=40)),
                ('city', models.CharField(default='Kampala', max_length=40)),
                ('address', models.CharField(default='None', max_length=50)),
                ('postal', models.CharField(default='None', max_length=50)),
                ('website', models.CharField(default='None', max_length=50)),
                ('organization_name', models.CharField(default='None', max_length=50)),
                ('organization_motto', models.CharField(blank=True, max_length=150, null=True)),
                ('mobile', models.CharField(blank=True, max_length=20, null=True)),
                ('office_phone_number1', models.CharField(blank=True, max_length=20, null=True)),
                ('office_phone_number2', models.CharField(blank=True, max_length=40, null=True)),
                ('organization_logo', models.ImageField(upload_to='logo')),
                ('app_name', models.CharField(default='Inventory', max_length=20)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('sku', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('barcode', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('uuid_code', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='app.category')),
            ],
        ),
        migrations.CreateModel(
            name='PurchaseOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('purchase_date', models.DateField(auto_now_add=True)),
                ('expected_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('RECEIVED', 'Received')], max_length=20)),
                ('recorded_by', models.CharField(max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='Sales',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sale_date', models.DateField(auto_now_add=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('FULFILLED', 'Fulfilled')], max_length=20)),
                ('recorded_by', models.CharField(max_length=50)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='app.customer')),
            ],
        ),
        migrations.CreateModel(
            name='StoreLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('address', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('contact_person', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(max_length=20)),
                ('address', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='UnitOfMeasure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('abbreviation', models.CharField(max_length=10)),
            ],
        ),
        migrations.CreateModel(
            name='StockTransfer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('transfer_date', models.DateField(auto_now_add=True)),
                ('from_store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outgoing_transfers', to='app.storelocation')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product')),
                ('to_store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='incoming_transfers', to='app.storelocation')),
            ],
        ),
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('movement_type', models.CharField(choices=[('IN', 'In'), ('OUT', 'Out'), ('TRANSFER', 'Transfer')], max_length=10)),
                ('quantity', models.IntegerField()),
                ('related_order_id', models.IntegerField(blank=True, null=True)),
                ('note', models.TextField(blank=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.storelocation')),
            ],
        ),
        migrations.CreateModel(
            name='SalesItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('sale_price', models.DecimalField(decimal_places=0, max_digits=10)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='app.sales')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product')),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.unitofmeasure')),
            ],
        ),
        migrations.AddField(
            model_name='sales',
            name='store',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.storelocation'),
        ),
        migrations.CreateModel(
            name='PurchaseOrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('unit_cost', models.DecimalField(decimal_places=0, max_digits=10)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='app.purchaseorder')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product')),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.unitofmeasure')),
            ],
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='supplier',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.supplier'),
        ),
        migrations.CreateModel(
            name='ProductUnitPrice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('conversion_factor', models.FloatField(default=1.0)),
                ('price', models.DecimalField(decimal_places=0, max_digits=10)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='unit_prices', to='app.product')),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.unitofmeasure')),
            ],
            options={
                'unique_together': {('product', 'unit')},
            },
        ),
        migrations.CreateModel(
            name='Inventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity_in_stock', models.IntegerField(default=0)),
                ('reorder_level', models.IntegerField(default=10)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.storelocation')),
            ],
            options={
                'unique_together': {('product', 'store')},
            },
        ),
    ]
