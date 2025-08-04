from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from app.models.human_resource import Employee

@receiver(post_save, sender=Employee)
def create_user_for_employee(sender, instance, created, **kwargs):
    if created and not instance.user:
       
        username = f"{instance.first_name.lower()}.{instance.last_name.lower()}"
        
        # Ensure username is unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=instance.email,
            first_name=instance.first_name,
            last_name=instance.last_name,
            password="user_123"
        )
        instance.user = user
        instance.save(update_fields=['user'])