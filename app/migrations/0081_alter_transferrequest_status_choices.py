from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0080_alter_stocktransfer_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transferrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("in_transit", "In Transit"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                    ("rejected", "Rejected"),
                    ("fulfilled", "Fulfilled"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
