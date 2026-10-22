"""
Business events that raise a notification.

The signals here turn a change in the data into a notification for the
people who should know about it. They all go through
``app.services.notification_service`` so that

* the preference of every recipient is respected, and
* nobody is told about their own action.

The events covered are the ones a user can switch on and off in the
settings workspace: sales, purchasing, low stock, transfers, roles and
business administration.
"""
from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver

from app.models.human_resource import UserProfile
from app.models.products import Inventory
from app.models.tenancy import Business
from app.models.transactions import PurchaseOrder, Sales, TransferRequest
from app.services import notification_service as notify_service

# Module ids of the RBAC model (see app/models/human_resource.py).
MODULE_INVENTORY = 2
MODULE_STOCK = 3
MODULE_SALES = 4

User = get_user_model()


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Sales)
def sale_recorded(sender, instance, created, **kwargs):
    """A new sale is worth telling the sales team about."""
    if not created:
        return
    business = getattr(instance.store, 'business', None)
    if business is None:
        return
    notify_service.notify_module(
        business,
        MODULE_SALES,
        notify_service.EVENT_SALES,
        'New sale recorded',
        f'{instance.receipt_no or "A sale"} was recorded for '
        f'{getattr(instance.store, "name", "a store")}.',
        notification_type=notify_service.TYPE_SUCCESS,
        link='/sales/',
        exclude=[instance.recorded_by],
        priority=notify_service.PRIORITY_NORMAL,
    )


# ---------------------------------------------------------------------------
# Purchasing
# ---------------------------------------------------------------------------

@receiver(post_save, sender=PurchaseOrder)
def purchase_order_created(sender, instance, created, **kwargs):
    """A new purchase order is worth telling the stock team about."""
    if not created:
        return
    business = getattr(instance.store, 'business', None)
    if business is None:
        return
    # ``recorded_by`` holds the username of the person who raised the order.
    actor = User.objects.filter(username=instance.recorded_by).first()
    notify_service.notify_module(
        business,
        MODULE_STOCK,
        notify_service.EVENT_PURCHASING,
        'New purchase order',
        f'Purchase order PO-{instance.pk} was raised for '
        f'{getattr(instance.supplier, "name", "a supplier")}.',
        notification_type=notify_service.TYPE_INFO,
        link='/purchase_orders/',
        exclude=[actor],
    )


# ---------------------------------------------------------------------------
# Low stock
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=Inventory)
def remember_stock_level(sender, instance, **kwargs):
    """Keep the level the stock had before the change."""
    if instance.pk:
        previous = Inventory.objects.filter(pk=instance.pk).values_list(
            'quantity_in_stock', flat=True,
        ).first()
        instance._previous_quantity = previous
    else:
        instance._previous_quantity = None


@receiver(post_save, sender=Inventory)
def stock_fell_below_reorder_level(sender, instance, created, **kwargs):
    """Tell the store keeper when a product falls below its reorder level."""
    previous = getattr(instance, '_previous_quantity', None)
    if previous is not None and previous <= instance.reorder_level:
        # It was already below the level, nothing new to say.
        return
    if not instance.is_below_reorder:
        return

    business = getattr(instance.store, 'business', None)
    if business is None:
        return
    notify_service.notify_module(
        business,
        MODULE_INVENTORY,
        notify_service.EVENT_LOW_STOCK,
        'Low stock',
        f'{instance.product.name} fell to {instance.quantity_in_stock} at '
        f'{getattr(instance.store, "name", "a store")} '
        f'(reorder level {instance.reorder_level}).',
        notification_type=notify_service.TYPE_WARNING,
        link='/stores/inventory/overview/',
        # Running out of stock is the one event nobody may miss.
        priority=notify_service.PRIORITY_HIGH,
    )


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=TransferRequest)
def remember_transfer_status(sender, instance, **kwargs):
    """Keep the status the request had before the change."""
    if instance.pk:
        instance._previous_status = TransferRequest.objects.filter(
            pk=instance.pk,
        ).values_list('status', flat=True).first()
    else:
        instance._previous_status = None


@receiver(post_save, sender=TransferRequest)
def transfer_request_changed(sender, instance, created, **kwargs):
    """Tell the requester about the decision, and the approvers about a request."""
    previous = getattr(instance, '_previous_status', None)

    if created:
        business = getattr(instance.from_store, 'business', None)
        if business is not None:
            notify_service.notify_module(
                business,
                MODULE_STOCK,
                notify_service.EVENT_TRANSFERS,
                'Transfer request raised',
                f'{instance.requested_by} asked for stock to move from '
                f'{getattr(instance.from_store, "name", "a store")} to '
                f'{getattr(instance.to_store, "name", "another store")}.',
                notification_type=notify_service.TYPE_INFO,
                link='/transfer_requests/',
                exclude=[instance.requested_by],
            )
        return

    if previous == instance.status:
        return

    if instance.status in ('approved', 'rejected', 'cancelled'):
        message = {
            'approved': 'was approved',
            'rejected': 'was rejected',
            'cancelled': 'was cancelled',
        }[instance.status]
        notify_service.notify(
            instance.requested_by,
            notify_service.EVENT_TRANSFERS,
            f'Transfer request {message}',
            f'Your transfer request from '
            f'{getattr(instance.from_store, "name", "a store")} to '
            f'{getattr(instance.to_store, "name", "another store")} {message}.',
            notification_type=(
                notify_service.TYPE_SUCCESS if instance.status == 'approved'
                else notify_service.TYPE_WARNING
            ),
            link='/transfer_requests/',
            priority=notify_service.PRIORITY_NORMAL,
            # The same request being told about twice is one event.
            dedupe_key=f'transfer:{instance.pk}:{instance.status}',
        )


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

@receiver(m2m_changed, sender=UserProfile.roles.through)
def roles_changed(sender, instance, action, reverse, pk_set, **kwargs):
    """Tell a user when their roles (and with them their access) change."""
    if reverse:
        return

    if action in ('pre_add', 'pre_remove', 'pre_clear'):
        # Remember the names now: after the change the roles are gone.
        from app.models.human_resource import Role
        if action == 'pre_clear':
            instance._changed_role_names = list(
                instance.roles.values_list('name', flat=True),
            )
        else:
            instance._changed_role_names = list(
                Role.objects.filter(pk__in=(pk_set or [])).values_list('name', flat=True),
            )
        return

    if action not in ('post_add', 'post_remove', 'post_clear'):
        return

    names = getattr(instance, '_changed_role_names', [])

    if action == 'post_add':
        message = 'You were given the role ' + (', '.join(names) or 'a new role') + '.'
        notification_type = notify_service.TYPE_SUCCESS
    elif action == 'post_remove':
        message = 'The role ' + (', '.join(names) or 'a role') + ' was taken from you.'
        notification_type = notify_service.TYPE_WARNING
    else:
        message = 'All your roles were removed.'
        notification_type = notify_service.TYPE_WARNING

    notify_service.notify(
        instance.user,
        notify_service.EVENT_ROLES,
        'Your access changed',
        message,
        notification_type=notification_type,
        link='/settings/tab/users/',
        # Losing or gaining access matters more than a routine event.
        priority=notify_service.PRIORITY_HIGH,
        dedupe_key=f'roles:{instance.pk}:{action}:{",".join(sorted(names))}',
    )


# ---------------------------------------------------------------------------
# Businesses
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=Business)
def remember_business_status(sender, instance, **kwargs):
    """Keep the status the business had before the change."""
    if instance.pk:
        instance._previous_status = Business.objects.filter(
            pk=instance.pk,
        ).values_list('status', flat=True).first()
    else:
        instance._previous_status = None


@receiver(post_save, sender=Business)
def business_changed(sender, instance, created, **kwargs):
    """Tell the platform about a new business, and its staff about a status change."""
    if created:
        notify_service.notify_platform_admins(
            notify_service.EVENT_BUSINESS,
            'New business registered',
            f'"{instance.name}" was registered on the platform.',
            notification_type=notify_service.TYPE_INFO,
            link='/platform/businesses/',
        )
        return

    previous = getattr(instance, '_previous_status', None)
    if previous == instance.status:
        return

    if instance.status == 'suspended':
        message = f'"{instance.name}" has been suspended.'
        notification_type = notify_service.TYPE_ERROR
    else:
        message = f'"{instance.name}" is active again.'
        notification_type = notify_service.TYPE_SUCCESS

    notify_service.notify_admins(
        instance,
        notify_service.EVENT_BUSINESS,
        'Business status changed',
        message,
        notification_type=notification_type,
        link='/settings/tab/profile/',
        priority=notify_service.PRIORITY_HIGH,
        dedupe_key=f'business:{instance.pk}:{instance.status}',
    )
