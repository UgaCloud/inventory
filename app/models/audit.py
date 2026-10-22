"""
Append-only audit trail.

Every meaningful business action can be recorded here. Entries are written
by ``app.services.audit_service`` (which is also used by the model-change
signals), never edited afterwards: the model refuses updates and deletes so
ordinary users cannot rewrite history.

Tenant scope: ``business`` is the tenant the event belongs to. Platform
events (business registration, a platform administrator signing in) keep
``business = NULL`` and are therefore visible to platform administrators
only.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from app.managers import TenantManager, TenantQuerySet


class AuditLogQuerySet(TenantQuerySet):
    """Append-only queryset: entries can be created but never removed."""

    def delete(self):
        raise ValidationError('Audit log entries are append-only and cannot be deleted.')


class AuditLog(models.Model):
    """A single recorded action."""

    class Category(models.TextChoices):
        AUTH = 'auth', 'Authentication'
        USER = 'user', 'Users & employees'
        ROLE = 'role', 'Roles & permissions'
        SETTINGS = 'settings', 'Settings'
        PRODUCT = 'product', 'Products & catalogue'
        INVENTORY = 'inventory', 'Inventory & stock'
        SALES = 'sales', 'Sales'
        PURCHASE = 'purchase', 'Purchasing'
        CUSTOMER = 'customer', 'Customers & payments'
        FINANCE = 'finance', 'Finance'
        PLATFORM = 'platform', 'Platform administration'
        DATA = 'data', 'Data & exports'

    class Action(models.TextChoices):
        CREATE = 'create', 'Created'
        UPDATE = 'update', 'Updated'
        DELETE = 'delete', 'Deleted'
        LOGIN = 'login', 'Signed in'
        LOGOUT = 'logout', 'Signed out'
        LOGIN_FAILED = 'login_failed', 'Failed sign-in'
        APPROVE = 'approve', 'Approved'
        REJECT = 'reject', 'Rejected'
        CANCEL = 'cancel', 'Cancelled'
        EXPORT = 'export', 'Exported'
        STATUS = 'status', 'Status changed'
        ACCESS = 'access', 'Access denied'

    class Outcome(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILURE = 'failure', 'Failure'

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_events',
    )
    actor_name = models.CharField(max_length=150, blank=True, default='')
    business = models.ForeignKey(
        'app.Business', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_events',
        help_text='Tenant this event belongs to (NULL = platform-wide event)',
    )
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.SETTINGS)
    action = models.CharField(max_length=32, choices=Action.choices, default=Action.UPDATE)
    model_name = models.CharField(max_length=100, blank=True, default='')
    object_id = models.CharField(max_length=64, blank=True, default='')
    description = models.TextField(blank=True, default='')
    changes = models.JSONField(default=dict, blank=True)
    outcome = models.CharField(max_length=16, choices=Outcome.choices, default=Outcome.SUCCESS)
    request_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default='')

    # Tenant-aware manager: business users only ever see the entries of
    # their own business, platform administrators see every entry
    # (including the platform-wide ones with business = NULL).
    objects = TenantManager.from_queryset(AuditLogQuerySet)()

    class Meta:
        ordering = ['-timestamp', '-id']
        verbose_name = 'Audit log entry'
        verbose_name_plural = 'Audit log entries'
        indexes = [
            models.Index(fields=['business', '-timestamp']),
            models.Index(fields=['category', '-timestamp']),
        ]

    def __str__(self):
        who = self.actor_name or 'system'
        return f'{self.timestamp:%Y-%m-%d %H:%M} {who} · {self.get_action_display()} {self.description}'

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError('Audit log entries are append-only.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Audit log entries cannot be deleted.')

    @property
    def target(self):
        """Human readable target of the audited record."""
        if self.model_name and self.object_id:
            return f'{self.model_name} #{self.object_id}'
        return self.model_name or ''
