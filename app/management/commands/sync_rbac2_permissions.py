"""
Management command to migrate from single-role to multi-role RBAC 2.0 system.

This command:
1. Converts old single-role field to new ManyToMany system
2. Populates effective permissions
3. Ensures Employee.user → UserProfile.employee linkage
4. Detects and fixes orphan profiles or employees
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app.models.human_resource import UserProfile, Role, Employee

class Command(BaseCommand):
    help = 'Migrate from single-role to RBAC 2.0 multi-role system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write(self.style.SUCCESS('Starting RBAC 2.0 migration...'))
        
        # Step 1: Convert single-role to M2M
        self.stdout.write('\n1. Converting single-role to M2M roles...')
        migrated_count = 0
        
        for profile in UserProfile.objects.all():
            # If profile has old role field but not in M2M
            if profile.role and profile.role not in profile.roles.all():
                if not dry_run:
                    profile.roles.add(profile.role)
                    profile.assigned_by = profile.assigned_by or User.objects.filter(is_superuser=True).first()
                    profile.save()
                migrated_count += 1
                self.stdout.write(f'  ✓ Migrated {profile.user.username}: {profile.role.name}')
        
        self.stdout.write(self.style.SUCCESS(f'  Migrated {migrated_count} profiles'))
        
        # Step 2: Populate effective permissions
        self.stdout.write('\n2. Populating effective permissions...')
        updated_count = 0
        
        for profile in UserProfile.objects.all():
            effective = profile.effective_modules
            if profile.access_modules != effective:
                if not dry_run:
                    UserProfile.objects.filter(pk=profile.pk).update(access_modules=effective)
                updated_count += 1
                self.stdout.write(f'  ✓ Updated {profile.user.username}: {len(effective)} modules')
        
        self.stdout.write(self.style.SUCCESS(f'  Updated {updated_count} profiles'))
        
        # Step 3: Fix Employee-UserProfile linkage
        self.stdout.write('\n3. Fixing Employee-UserProfile linkage...')
        fixed_count = 0
        
        for employee in Employee.objects.filter(user__isnull=False):
            try:
                profile = employee.user.profile
                if profile.employee != employee:
                    if not dry_run:
                        profile.employee = employee
                        profile.save()
                    fixed_count += 1
                    self.stdout.write(f'  ✓ Fixed linkage for {employee.user.username}')
            except UserProfile.DoesNotExist:
                # Create profile if missing
                if not dry_run:
                    UserProfile.objects.create(user=employee.user, employee=employee)
                fixed_count += 1
                self.stdout.write(f'  ✓ Created profile for {employee.user.username}')
        
        self.stdout.write(self.style.SUCCESS(f'  Fixed {fixed_count} linkages'))
        
        # Step 4: Detect orphan profiles
        self.stdout.write('\n4. Detecting orphan profiles...')
        orphan_count = 0
        
        for profile in UserProfile.objects.all():
            if not profile.user:
                orphan_count += 1
                self.stdout.write(self.style.WARNING(f'  ⚠ Orphan profile (ID: {profile.pk}) - no user'))
                if not dry_run:
                    profile.delete()
                    self.stdout.write(f'    Deleted orphan profile')
        
        self.stdout.write(self.style.SUCCESS(f'  Found and handled {orphan_count} orphan profiles'))
        
        # Step 5: Detect employees without users but should have
        self.stdout.write('\n5. Checking employees without users...')
        employee_count = 0
        
        for employee in Employee.objects.filter(user__isnull=True):
            employee_count += 1
            self.stdout.write(self.style.WARNING(f'  ⚠ Employee {employee.pk} has no user account'))
        
        if employee_count > 0:
            self.stdout.write(self.style.WARNING(f'  Found {employee_count} employees without user accounts'))
        else:
            self.stdout.write(self.style.SUCCESS('  All employees have user accounts'))
        
        # Summary
        self.stdout.write('\n' + '='*50)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETE - No changes were made'))
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write(self.style.SUCCESS('RBAC 2.0 migration complete!'))
        self.stdout.write('='*50)


