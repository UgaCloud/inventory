"""
Make role names unique per business and scope the backing Django groups.

Two changes, both additive:

1. ``Role.name`` is no longer globally unique. A name is unique inside a
   business (``business`` + ``name``); platform roles (``business = NULL``)
   keep a globally unique name. Business administrators can therefore create
   their own "Sales Officer" without colliding with another tenant.

2. The Django ``Group`` backing a role is renamed to ``<tenant>:<role name>``.
   Groups are global, so a shared group would hand the permissions of one
   business to the employees of another one. Renaming keeps every role's
   permissions private; group membership is untouched.
"""
from django.db import migrations, models


def scope_groups(apps, schema_editor):
    """Rename every role's group so it carries its tenant prefix."""
    Role = apps.get_model('app', 'Role')
    Group = apps.get_model('auth', 'Group')

    used = set()
    for role in Role.objects.select_related('business').order_by('pk'):
        if not role.group_id:
            continue
        prefix = role.business.slug if role.business_id else 'platform'
        new_name = f'{prefix}:{role.name}'[:150]
        candidate = new_name
        suffix = 1
        while candidate in used:
            suffix += 1
            candidate = f'{new_name}-{suffix}'[:150]
        used.add(candidate)

        group = Group.objects.filter(pk=role.group_id).first()
        if group is None:
            continue
        group.name = candidate
        group.save(update_fields=['name'])


def restore_groups(apps, schema_editor):
    """Restore the original (unprefixed) group names."""
    Role = apps.get_model('app', 'Role')
    Group = apps.get_model('auth', 'Group')
    for role in Role.objects.select_related('business').order_by('pk'):
        if not role.group_id:
            continue
        group = Group.objects.filter(pk=role.group_id).first()
        if group is None:
            continue
        name = role.name
        if group.name != name:
            group.name = name[:150]
            group.save(update_fields=['name'])


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0097_bankaccount_business'),
    ]

    operations = [
        migrations.AlterField(
            model_name='role',
            name='name',
            field=models.CharField(max_length=150),
        ),
        migrations.AddConstraint(
            model_name='role',
            constraint=models.UniqueConstraint(
                condition=models.Q(business__isnull=False),
                fields=('business', 'name'),
                name='uniq_role_name_per_business',
            ),
        ),
        migrations.AddConstraint(
            model_name='role',
            constraint=models.UniqueConstraint(
                condition=models.Q(business__isnull=True),
                fields=('name',),
                name='uniq_platform_role_name',
            ),
        ),
        migrations.RunPython(scope_groups, restore_groups),
    ]
