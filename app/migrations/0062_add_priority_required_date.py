from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0061_transferrequest_department"),
    ]

    operations = [
        migrations.AddField(
            model_name='transferrequest',
            name='priority',
            field=models.CharField(choices=[('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')], default='normal', max_length=10),
        ),
        migrations.AddField(
            model_name='transferrequest',
            name='required_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
