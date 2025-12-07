"""
Signals for user management and role assignment.
"""
from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from app.models.human_resource import UserProfile, Role, Employee

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when a User is created"""
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=UserProfile)
def sync_user_permissions(sender, instance, created, **kwargs):
    """Sync user permissions when roles are assigned or updated (RBAC 2.0)"""
    if instance.roles.exists():
        # Update access modules from all roles (RBAC 2.0)
        instance.update_modules_from_roles()
        
        # Apply each role's permissions to user
        for role in instance.roles.all():
            role.apply_to_user(instance.user)

@receiver(post_save, sender=Role)
def update_role_users(sender, instance, **kwargs):
    """Update all users with this role when role modules change"""
    # This will be triggered when role is saved
    # The role's update_all_users() method is called in set_modules()
    pass

@receiver(post_save, sender=Employee)
def sync_employee_user_profile(sender, instance, created, **kwargs):
    """Sync Employee with UserProfile when employee is created or updated"""
    if instance.user:
        # Get or create user profile
        profile, created = UserProfile.objects.get_or_create(user=instance.user)
        
        # Link employee to profile if not already linked
        if not profile.employee:
            profile.employee = instance
            profile.save(update_fields=['employee'])
        
        # Update department in profile
        if instance.department:
            profile.department = instance.department.name
            profile.save(update_fields=['department'])

@receiver(pre_save, sender=UserProfile)
def sync_employee_department(sender, instance, **kwargs):
    """Auto-populate department from employee if available"""
    if instance.employee and not instance.department:
        if instance.employee.department:
            instance.department = instance.employee.department.name

@receiver(m2m_changed, sender=UserProfile.roles.through)
def update_modules_on_role_change(sender, instance, action, **kwargs):
    """Update modules when roles M2M changes (RBAC 2.0)"""
    if action in ('post_add', 'post_remove', 'post_clear'):
        instance.update_modules_from_roles()
        # Apply permissions from all roles
        for role in instance.roles.all():
            role.apply_to_user(instance.user)

