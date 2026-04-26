from django.db import migrations


def migrate_country_codes_to_names(apps, schema_editor):
    OrganizationSetting = apps.get_model('app', 'OrganizationSetting')
    country_mapping = {
        'UG': 'Uganda',
        'KE': 'Kenya',
        'TZ': 'Tanzania',
        'RD': 'Rwanda',
        'BD': 'Burundi',
        'SD': 'South Sudan',
    }
    for old_code, new_name in country_mapping.items():
        OrganizationSetting.objects.filter(country=old_code).update(country=new_name)


def migrate_currency_ksh_to_kes(apps, schema_editor):
    OrganizationSetting = apps.get_model('app', 'OrganizationSetting')
    OrganizationSetting.objects.filter(currency='KSH').update(currency='KES')


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0089_alter_organizationsetting_organization_logo'),
    ]

    operations = [
        migrations.RunPython(
            migrate_country_codes_to_names,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            migrate_currency_ksh_to_kes,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
