from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="transferrequest",
            name="department",
            field=models.ForeignKey(
                to="app.Department",
                on_delete=models.deletion.CASCADE,
                related_name="transfer_requests",
                null=True,
                blank=True,
            ),
        ),
    ]
