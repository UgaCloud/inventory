import uuid

from django.db import migrations, models


def _generate_unique_barcode(Product, current_pk=None):
    while True:
        candidate = str(uuid.uuid4().int)[:13]
        queryset = Product.objects.filter(barcode=candidate)
        if current_pk is not None:
            queryset = queryset.exclude(pk=current_pk)
        if not queryset.exists():
            return candidate


def backfill_missing_barcodes(apps, schema_editor):
    Product = apps.get_model("app", "Product")
    products = Product.objects.filter(models.Q(barcode__isnull=True) | models.Q(barcode=""))
    for product in products.iterator():
        product.barcode = _generate_unique_barcode(Product, product.pk)
        product.save(update_fields=["barcode"])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0081_alter_transferrequest_status_choices"),
    ]

    operations = [
        migrations.RunPython(backfill_missing_barcodes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="barcode",
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
