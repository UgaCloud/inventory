from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from app.models.human_resource import Employee

@receiver(post_save, sender=Employee)
def create_user_for_employee(sender, instance, created, **kwargs):
    if created and not instance.user:
        # Use department name as part of username for uniqueness if needed
        base_username = f"{instance.department.name.lower()}_employee{instance.pk}"
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        # Create user
        user = User.objects.create_user(
            username=username,
            password="user_123"
        )
        instance.user = user
        instance.save(update_fields=['user'])