"""
Automatic tenant assignment.

When a business user creates a tenant-owned row (product, customer, store,
role, user profile…) the row must belong to their business, otherwise it
would be invisible to its own creator. The acting user is published by
``app.middleware.TenantMiddleware``; outside a request (management commands,
imports) nothing is assigned and rows keep ``business = NULL`` — such rows
stay visible to platform administrators only.
"""
from django.db.models.signals import pre_save
from django.dispatch import receiver


@receiver(pre_save)
def assign_tenant_business(sender, instance, **kwargs):
    """Stamp new tenant-owned rows with the acting user's business."""
    if not hasattr(instance, 'business_id'):
        return
    if instance.business_id:
        return

    from app.managers import actor_business, current_tenant_actor, is_platform_admin

    user = current_tenant_actor()
    if user is None or not getattr(user, 'is_authenticated', False):
        return
    if is_platform_admin(user):
        # Platform administrators may target any business explicitly; the
        # default must not silently become the platform operator's tenant.
        return

    business = actor_business(user)
    if business is not None:
        instance.business_id = business.pk
