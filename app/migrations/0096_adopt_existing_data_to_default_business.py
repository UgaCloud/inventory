"""
Data migration: provision the Default Business and adopt all existing rows.

Additive and non-destructive: every pre-existing Branch, StoreLocation, Product,
Customer, Supplier, Role and UserProfile is attached to the auto-created
"Default Business" tenant, so all current data keeps working unchanged.
"""
from django.db import migrations


def adopt_existing_data(apps, schema_editor):
    Business = apps.get_model('app', 'Business')
    business, _ = Business.objects.get_or_create(
        slug='default',
        defaults={'name': 'Default Business'},
    )

    for model_name in ('Branch', 'StoreLocation', 'Product', 'Customer',
                       'Supplier', 'Role', 'UserProfile'):
        Model = apps.get_model('app', model_name)
        Model.objects.filter(business__isnull=True).update(business=business)


def unadopt(apps, schema_editor):
    # Reverse: detach the rows again so the tenant concept disappears without
    # touching the business data itself.
    Business = apps.get_model('app', 'Business')
    for model_name in ('Branch', 'StoreLocation', 'Product', 'Customer',
                       'Supplier', 'Role', 'UserProfile'):
        Model = apps.get_model('app', model_name)
        Model.objects.filter(business__isnull=False).update(business=None)

    # OrganizationSetting.business cascades: deleting the tenant row would
    # delete the company's profile with it. Detach the profile first so the
    # rollback never destroys a company profile.
    OrganizationSetting = apps.get_model('app', 'OrganizationSetting')
    OrganizationSetting.objects.filter(business__isnull=False).update(business=None)

    Business.objects.filter(slug='default').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0095_userprofile_is_platform_admin_business_and_more'),
    ]

    operations = [
        migrations.RunPython(adopt_existing_data, unadopt),
    ]
