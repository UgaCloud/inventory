from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0088_automotive_alter_category_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organizationsetting',
            name='organization_logo',
            field=models.ImageField(blank=True, null=True, upload_to='logo'),
        ),
    ]
