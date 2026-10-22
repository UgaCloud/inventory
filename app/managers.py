"""
Tenant-aware managers for the shared-database multi-tenant setup.

Every tenant-owned row carries a ``business`` FK — either directly (Product,
StoreLocation, Customer…) or through a related row (Sales -> store ->
business, SalesItem -> sale -> store -> business, …).

Instead of remembering to scope every single queryset by hand, the models
below use ``TenantManager``. It filters any queryset to the acting user's
business. The acting user is published for the duration of the request by
``app.middleware.TenantMiddleware`` through a thread-local, which keeps the
manager completely decoupled from views, selectors and services.

Rules
-----
* Platform Super Administrators (``is_superuser`` or
  ``profile.is_platform_admin``) see every row.
* Business users only see rows that belong to their own business.
* Rows that cannot be attributed to a business are visible to platform
  administrators only, unless the tenant link itself is optional (for
  example a payment without a customer): those rows are not owned by any
  business, so every business may see them.
* Outside a request (management commands, background jobs, unit tests) no
  scoping is applied, so maintenance code keeps working unchanged.
"""
from asgiref.local import Local
from django.db import models
from django.db.models import Q

# Thread-local holding the user the current request acts as. ``asgiref.local``
# is used instead of ``threading.local`` so the value follows async workers.
_actor = Local()


def set_tenant_actor(user):
    """Publish the acting user for the current request/thread."""
    _actor.user = user


def clear_tenant_actor():
    """Forget the acting user (called at the end of every request)."""
    _actor.user = None


def current_tenant_actor():
    """The user the current thread acts as, or ``None`` outside a request."""
    return getattr(_actor, 'user', None)


def is_platform_admin(user):
    """True for platform Super Administrators (never for business staff)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    return bool(getattr(profile, 'is_platform_admin', False))


def actor_business(user):
    """The business the acting user belongs to (default business fallback)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    profile = getattr(user, 'profile', None)
    business = getattr(profile, 'business', None) if profile is not None else None
    if business is not None:
        return business
    from app.models.tenancy import Business
    return Business.get_default()


# ---------------------------------------------------------------------------
# Tenant paths
# ---------------------------------------------------------------------------
# model name (lower case) -> tuple of (lookup path, allow-null rows).
#
# "allow-null rows" means: rows whose tenant link is optional are not owned
# by any business, so they stay visible to every business instead of
# disappearing for everyone.
TENANT_PATHS = {
    # -- direct tenant ownership -------------------------------------------
    'product': (('business', False),),
    'storelocation': (('business', False),),
    'branch': (('business', False),),
    'customer': (('business', False),),
    'supplier': (('business', False),),
    'role': (('business', True),),
    'bankaccount': (('business', False),),
    'auditlog': (('business', False),),
    'userprofile': (('business', True),),
    # -- through a related tenant-owned row --------------------------------
    'customerledger': (('customer__business', True),),
    'payment': (('customer__business', True),),
    'paymentallocation': (
        ('payment__customer__business', True),
        ('sale__store__business', False),
    ),
    'productunitprice': (('product__business', False),),
    'inventory': (('store__business', False),),
    'purchaseorder': (('store__business', False),),
    'purchaseorderitem': (('order__store__business', False),),
    'inventorybatch': (('store__business', False),),
    'sales': (('store__business', False),),
    'salesitem': (('order__store__business', False),),
    'transferrequest': (('from_store__business', False),),
    'transferrequestitem': (('transfer_request__from_store__business', False),),
    'stocktransfer': (('from_store__business', False),),
    'stocktransferitem': (('stock_transfer__from_store__business', False),),
    'stockadjustment': (('store__business', False),),
    'stockadjustmentitem': (('stock_adjustment__store__business', False),),
    'stockmovement': (('store__business', False),),
    'salesreturn': (('sale__store__business', False),),
    'perfumesaleline': (('sale__store__business', False),),
    'perfumesalecomponent': (('line__sale__store__business', False),),
    'rolemodule': (('role__business', True),),
    'roledeletionlog': (('role__business', True),),
    'employee': (
        ('user_profile__business', True),
        ('branch__business', True),
    ),
    'cashflow': (('store__business', False),),
    'dailycashsummary': (('store__business', False),),
    'banktransaction': (
        ('bank_account__business', True),
        ('store__business', False),
    ),
    'expense': (('store__business', False),),
}


def tenant_spec(model):
    """Tenant lookup spec for a model class (empty tuple when not scoped)."""
    return TENANT_PATHS.get(model.__name__.lower(), ())


def apply_tenant_filter(queryset, business, spec=None):
    """Restrict ``queryset`` to rows owned by ``business``."""
    if business is None:
        return queryset.none()
    if spec is None:
        spec = tenant_spec(queryset.model)
    if not spec:
        return queryset

    condition = Q()
    for path, allow_null in spec:
        part = Q(**{path: business})
        if allow_null:
            part |= Q(**{f'{path}__isnull': True})
        condition |= part
    return queryset.filter(condition)


class TenantQuerySet(models.QuerySet):
    """QuerySet with explicit tenant helpers (used by maintenance code)."""

    def for_business(self, business):
        """Restrict to one business; ``None`` keeps every row."""
        if business is None:
            return self
        return apply_tenant_filter(self, business)

    def for_current_business(self):
        """Restrict to the business of the acting user."""
        return self.for_business(actor_business(current_tenant_actor()))


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """Default manager that scopes querysets to the acting user's business."""

    def get_queryset(self):
        queryset = super().get_queryset()
        user = current_tenant_actor()
        if user is None or not getattr(user, 'is_authenticated', False):
            return queryset
        if is_platform_admin(user):
            return queryset
        if not tenant_spec(queryset.model):
            return queryset
        business = actor_business(user)
        if business is None:
            return queryset.none()
        return apply_tenant_filter(queryset, business)
