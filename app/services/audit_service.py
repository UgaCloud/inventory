"""
Centralized audit service.

All audit entries are written through :func:`log_event` so that the format,
the tenant attribution and the redaction rules are identical everywhere.
The service is deliberately defensive: an audit failure must never break a
business operation, so every write is wrapped in ``try/except``.

Typical use::

    from app.services.audit_service import log_event

    log_event(
        'update',
        category='settings',
        description='Updated organization settings',
        obj=organization_settings,
        request=request,
    )
"""
import logging
import uuid

from django.db import models

logger = logging.getLogger(__name__)

# Field names whose values must never end up in an audit trail.
SENSITIVE_FIELDS = {
    'password', 'password1', 'password2', 'new_password', 'old_password',
    'token', 'secret', 'api_key', 'apikey', 'access_token', 'refresh_token',
    'key', 'signature', 'otp', 'pin', 'ssn', 'card_number', 'cvv',
}

MAX_VALUE_LENGTH = 300


def redact_value(value):
    """Return a short, safe representation of a field value."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:MAX_VALUE_LENGTH]
    if isinstance(value, (list, tuple, set)):
        return [redact_value(v) for v in list(value)[:20]]
    if isinstance(value, dict):
        return {str(k)[:60]: redact_value(v) for k, v in list(value.items())[:20]}
    return str(value)[:MAX_VALUE_LENGTH]


def sanitize_changes(changes):
    """Drop sensitive keys and shorten long values."""
    if not changes:
        return {}
    clean = {}
    for key, value in (changes or {}).items():
        if str(key).lower() in SENSITIVE_FIELDS:
            clean[str(key)] = '[redacted]'
        else:
            clean[str(key)] = redact_value(value)
    return clean


def comparable_value(field, instance):
    """
    Value of a field in a shape that can be compared with the stored row.

    ``FileField`` (and therefore ``ImageField``) exposes a ``FieldFile``
    wrapper on the instance while the database only ever holds the path
    string. Comparing the two directly would report a change on every
    single save, so the file name is used instead.
    """
    value = getattr(instance, field.attname, None)
    if isinstance(field, models.FileField):
        return getattr(value, 'name', '') or ''
    return value


def model_changes(instance, fields=None):
    """
    Diff of the fields of an instance that actually changed.

    ``instance`` must be loaded with ``pre_save``/``post_save`` semantics:
    the service is called from a ``pre_save`` receiver that has the old
    values available in ``audit._old_values``.
    """
    old = getattr(instance, '_audit_old_values', None) or {}
    new = {}
    for field in instance._meta.concrete_fields:
        if fields and field.name not in fields:
            continue
        if field.primary_key:
            continue
        # auto_now / auto_now_add columns change on every write - they would
        # drown the meaningful diff.
        if getattr(field, 'auto_now', False) or getattr(field, 'auto_now_add', False):
            continue
        value = comparable_value(field, instance)
        if field.name in old and old[field.name] != value:
            new[field.name] = {'from': old[field.name], 'to': value}
    return sanitize_changes(new)


def current_actor():
    """
    The user the current request/thread acts as, or ``None``.

    Model-change signals have no request object at hand, so the acting user
    published by ``app.middleware.TenantMiddleware`` is used to attribute
    the event to a person and to a tenant.
    """
    try:
        from app.managers import current_tenant_actor
        return current_tenant_actor()
    except Exception:  # pragma: no cover - defensive
        return None


def _resolve_business(actor, business=None):
    """Business the event belongs to."""
    if business is not None:
        return business
    if actor is None or not getattr(actor, 'is_authenticated', False):
        return None
    try:
        from app.models.tenancy import user_is_platform_admin
        if user_is_platform_admin(actor):
            # Platform administrators act platform-wide: their events are
            # kept without a tenant so they are not hidden from other
            # platform administrators.
            return None
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        profile = actor.profile
    except Exception:
        return None
    business_id = getattr(profile, 'business_id', None)
    if not business_id:
        return None
    return getattr(profile, 'business', None)


def log_event(action, *, category='settings', description='', obj=None, actor=None,
              business=None, changes=None, request=None, outcome='success',
              model_name=None, object_id=None, request_id=None):
    """Record one audit event. Never raises."""
    try:
        from app.models.audit import AuditLog

        if request is not None and actor is None:
            actor = getattr(request, 'user', None)
        if request is not None and business is None:
            business = getattr(request, 'business', None)
        if actor is None:
            # Signals have no request; fall back to the acting user of the
            # current thread so the entry is attributed to a person/tenant.
            actor = current_actor()
        if business is None:
            business = _resolve_business(actor)

        if model_name is None and obj is not None:
            model_name = obj._meta.model_name
        if object_id is None and obj is not None:
            object_id = str(getattr(obj, 'pk', '') or '')

        ip_address = None
        user_agent = ''
        if request is not None:
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
            ip_address = (forwarded.split(',')[0].strip()
                          if forwarded else request.META.get('REMOTE_ADDR'))
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:300]
            request_id = request_id or request.META.get('HTTP_X_REQUEST_ID', '')

        if not request_id:
            request_id = uuid.uuid4().hex[:16]

        actor_name = ''
        if actor is not None and getattr(actor, 'is_authenticated', False):
            actor_name = (getattr(actor, 'get_full_name', lambda: '')() or
                          getattr(actor, 'username', '') or '')[:150]

        return AuditLog.objects.create(
            actor=actor if getattr(actor, 'is_authenticated', False) else None,
            actor_name=actor_name,
            business=business,
            category=category,
            action=action,
            model_name=(model_name or '')[:100],
            object_id=(object_id or '')[:64],
            description=(description or '')[:2000],
            changes=sanitize_changes(changes),
            outcome=outcome,
            request_id=request_id[:64],
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:  # pragma: no cover - auditing must never break a flow
        logger.exception('Could not write audit event (%s)', action)
        return None


def log_model_change(instance, action, request=None, actor=None, category=None,
                     description=None, extra_changes=None):
    """Record a model level change (create / update / delete)."""
    meta = instance._meta
    model_name = meta.model_name
    if category is None:
        category = category_for_model(meta)
    if description is None:
        label = str(instance) if action != 'delete' else f'{model_name} #{instance.pk}'
        description = f'{meta.verbose_name.capitalize()}: {label}'[:2000]

    changes = {}
    if action == 'update':
        changes = model_changes(instance)
    if extra_changes:
        changes.update(sanitize_changes(extra_changes))

    return log_event(
        action,
        category=category,
        description=description,
        obj=instance,
        actor=actor,
        request=request,
        changes=changes,
    )


CATEGORY_BY_MODEL = {
    'product': 'product',
    'category': 'product',
    'unitofmeasure': 'product',
    'productunitprice': 'product',
    'storelocation': 'inventory',
    'inventory': 'inventory',
    'inventorybatch': 'inventory',
    'stockmovement': 'inventory',
    'stockadjustment': 'inventory',
    'stockadjustmentitem': 'inventory',
    'stocktransfer': 'inventory',
    'stocktransferitem': 'inventory',
    'transferrequest': 'inventory',
    'transferrequestitem': 'inventory',
    'sales': 'sales',
    'salesitem': 'sales',
    'salesreturn': 'sales',
    'salesreturnitem': 'sales',
    'perfumesaleline': 'sales',
    'perfumesalecomponent': 'sales',
    'purchaseorder': 'purchase',
    'purchaseorderitem': 'purchase',
    'supplier': 'purchase',
    'customer': 'customer',
    'customerledger': 'customer',
    'payment': 'customer',
    'paymentallocation': 'customer',
    'expense': 'finance',
    'expensecategory': 'finance',
    'cashflow': 'finance',
    'bankaccount': 'finance',
    'banktransaction': 'finance',
    'role': 'role',
    'rolemodule': 'role',
    'userprofile': 'user',
    'employee': 'user',
    'department': 'user',
    'designation': 'user',
    'branch': 'settings',
    'organizationsetting': 'settings',
    'business': 'platform',
}


def category_for_model(meta):
    """Audit category for a model class."""
    return CATEGORY_BY_MODEL.get(meta.model_name, 'settings')
