"""
Audit signals.

Two complementary sources feed the audit trail:

* Authentication events (sign-in, sign-out, failed sign-in) are captured
  from Django's own auth signals, so every entry point is covered.
* Record changes of the business-critical models are captured generically
  with a ``pre_save``/``post_save``/``post_delete`` trio. The old field
  values are read in ``pre_save`` and compared in ``post_save``, which keeps
  the before/after values without touching the views.

Business actions that need extra context (a sale being completed, a
business being suspended, a report being exported) are recorded explicitly
through ``app.services.audit_service.log_event`` in the corresponding view.
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from app.services import audit_service

# Models whose create/update/delete is recorded automatically.
AUDITED_MODELS = (
    'app.Product',
    'app.Category',
    'app.UnitOfMeasure',
    'app.ProductUnitPrice',
    'app.StoreLocation',
    'app.Inventory',
    'app.Branch',
    'app.OrganizationSetting',
    'app.Customer',
    'app.Supplier',
    'app.Sales',
    'app.StockAdjustment',
    'app.StockTransfer',
    'app.PurchaseOrder',
    'app.TransferRequest',
    'app.SalesReturn',
    'app.Payment',
    'app.Expense',
    'app.Role',
    'app.UserProfile',
    'app.Employee',
    'app.Business',
)


def _model_classes():
    from django.apps import apps
    resolved = []
    for label in AUDITED_MODELS:
        try:
            resolved.append(apps.get_model(label))
        except LookupError:  # pragma: no cover - model moved/renamed
            continue
    return resolved


def _connect():
    for model in _model_classes():
        pre_save.connect(
            _remember_old_values, sender=model, dispatch_uid=f'audit_pre_{model._meta.label_lower}'
        )
        post_save.connect(
            _record_save, sender=model, dispatch_uid=f'audit_post_{model._meta.label_lower}'
        )
        post_delete.connect(
            _record_delete, sender=model, dispatch_uid=f'audit_del_{model._meta.label_lower}'
        )


def _remember_old_values(sender, instance, **kwargs):
    """
    Remember the values the row currently has in the database.

    The in-memory instance already carries the *new* values at this point
    (a ModelForm has populated it), so the previous values have to be read
    back from the database - otherwise the diff would always be empty.
    """
    if not instance.pk:
        instance._audit_old_values = {}
        return
    old = {}
    try:
        db_row = sender._default_manager.filter(pk=instance.pk).values(
            *[f.attname for f in instance._meta.concrete_fields if not f.primary_key]
        ).first()
    except Exception:  # pragma: no cover - defensive
        db_row = None
    if not db_row:
        instance._audit_old_values = {}
        return
    for field in instance._meta.concrete_fields:
        if field.primary_key:
            continue
        old[field.name] = db_row.get(field.attname)
    instance._audit_old_values = old


def _record_save(sender, instance, created, **kwargs):
    if getattr(instance, '_audit_skip', False):
        # The change was made by the framework itself (e.g. the automatic
        # bootstrap of a singleton row) and not by a user.
        return

    actor = audit_service.current_actor()
    if created:
        audit_service.log_model_change(instance, 'create', actor=actor)
        return

    if not audit_service.model_changes(instance):
        # The row was saved without any field actually changing.
        return
    audit_service.log_model_change(instance, 'update', actor=actor)


def _record_delete(sender, instance, **kwargs):
    audit_service.log_model_change(instance, 'delete', actor=audit_service.current_actor())


# ---------------------------------------------------------------------------
# Authentication events
# ---------------------------------------------------------------------------

@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    audit_service.log_event(
        'login',
        category='auth',
        description=f'{user.get_username()} signed in',
        actor=user,
        request=request,
    )


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    audit_service.log_event(
        'logout',
        category='auth',
        description=f'{user.get_username()} signed out',
        actor=user,
        request=request,
    )


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get('username', '')
    audit_service.log_event(
        'login_failed',
        category='auth',
        description=f'Failed sign-in attempt for "{username}"',
        actor=None,
        request=request,
        outcome='failure',
    )


_connect()
