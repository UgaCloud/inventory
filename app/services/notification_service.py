"""
The one place that raises a notification.

Every part of the application that wants to tell somebody something calls
``notify`` (or one of the helpers below) instead of writing a
``Notification`` row of its own. The service

* checks the switch the user left for that kind of event in their personal
  settings, so nobody is told about a category they turned off;
* never notifies the person who caused the event;
* returns the notifications it created, so a caller can tell whether anybody
  was reached at all.

The events map onto the notification preferences of
``app.models.preferences.UserPreference``.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from app.models.notification import Notification
from app.models.preferences import UserPreference

# --- The kinds of event a user can switch on or off -----------------------
EVENT_SALES = 'sales'
EVENT_PURCHASING = 'purchasing'
EVENT_LOW_STOCK = 'low_stock'
EVENT_TRANSFERS = 'transfers'
EVENT_ROLES = 'roles'
EVENT_BUSINESS = 'business'

PREFERENCE_FIELD = {
    EVENT_SALES: 'notify_sales',
    EVENT_PURCHASING: 'notify_purchasing',
    EVENT_LOW_STOCK: 'notify_low_stock',
    EVENT_TRANSFERS: 'notify_transfers',
    EVENT_ROLES: 'notify_roles',
    EVENT_BUSINESS: 'notify_business',
}

# --- Notification kinds ----------------------------------------------------
TYPE_SUCCESS = 'success'
TYPE_ERROR = 'error'
TYPE_WARNING = 'warning'
TYPE_INFO = 'info'

# How urgent an event is.
PRIORITY_LOW = 'low'
PRIORITY_NORMAL = 'normal'
PRIORITY_HIGH = 'high'

# Two notifications that carry the same dedupe key describe the same event.
# Within this window the first one wins, so a repeating event (a product that
# stays below its reorder level, a transfer that is checked twice) does not
# fill the bell with copies of itself.
DEDUPE_WINDOW = timedelta(hours=24)


def user_wants(user, event):
    """Has this user left the switch of this event on?"""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    field = PREFERENCE_FIELD.get(event)
    if field is None:
        return True
    preference = UserPreference.objects.filter(user=user).first()
    if preference is None:
        # A user without preferences gets everything.
        return True
    return getattr(preference, field, True)


def notify(user, event, title, message, notification_type=TYPE_INFO, link=None,
           priority=PRIORITY_NORMAL, dedupe_key=''):
    """
    Raise one notification for one user.

    Returns the notification, or ``None`` when the user does not want this
    kind of event (or is not a real user).

    ``dedupe_key`` names the event. When the same key was already delivered
    to the same user within :data:`DEDUPE_WINDOW`, the notification that is
    already there is returned instead of a second copy.
    """
    if not user_wants(user, event):
        return None

    dedupe_key = (dedupe_key or '')[:120]
    if dedupe_key:
        existing = Notification.objects.filter(
            user=user,
            dedupe_key=dedupe_key,
            created_at__gte=timezone.now() - DEDUPE_WINDOW,
        ).first()
        if existing is not None:
            return existing

    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
        priority=priority,
        dedupe_key=dedupe_key,
    )


def notify_users(users, event, title, message, exclude=(), **kwargs):
    """Raise the same notification for a group of users."""
    excluded = {user.pk for user in exclude if user is not None}
    created = []
    for user in users:
        if user.pk in excluded:
            continue
        notification = notify(user, event, title, message, **kwargs)
        if notification is not None:
            created.append(notification)
    return created


def business_of(user):
    """The business a user belongs to (None for platform administrators)."""
    profile = getattr(user, 'profile', None)
    return getattr(profile, 'business', None)


def users_of_business(business):
    """The active users of a business."""
    if business is None:
        return []
    User = get_user_model()
    return list(User.objects.filter(profile__business=business, is_active=True))


def notify_module(business, module_id, event, title, message, exclude=(), **kwargs):
    """
    Notify the users of a business that hold a given module.

    This is how "the sales team is told about a new sale" is expressed
    without every view having to know who belongs where.
    """
    from app.utils.module_mapping import user_has_module_access

    excluded = {user.pk for user in exclude if user is not None}
    targets = [
        user for user in users_of_business(business)
        if user.pk not in excluded and user_has_module_access(user, module_id)
    ]
    return notify_users(targets, event, title, message, **kwargs)


def notify_platform_admins(event, title, message, **kwargs):
    """Notify the platform Super Administrators."""
    from app.models.tenancy import user_is_platform_admin

    User = get_user_model()
    targets = [
        user for user in User.objects.filter(is_active=True)
        if user_is_platform_admin(user)
    ]
    return notify_users(targets, event, title, message, **kwargs)


def notify_admins(business, event, title, message, **kwargs):
    """Notify the administrators (users & role management) of a business."""
    from app.utils.module_mapping import user_has_module_access

    targets = [
        user for user in users_of_business(business)
        if user_has_module_access(user, 7) or user_has_module_access(user, 15)
    ]
    return notify_users(targets, event, title, message, **kwargs)
