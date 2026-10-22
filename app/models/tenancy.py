"""
Multi-tenancy foundations: the Business (tenant) model and scoping helpers.

Design decisions (kept deliberately conservative for a shared codebase):
- Shared database, additive nullable FKs. Existing rows adopt the auto-provisioned
  "Default Business" via data migration, so no data is destroyed.
- Transactions (Sales, PurchaseOrder, Expense, CashFlow…) derive their tenant from
  their store/customer FKs rather than carrying their own business FK — this keeps
  the migration surface small and the invariant single (store -> business).
- The platform Super Administrator (user.is_superuser or profile.is_platform_admin)
  legitimately sees all businesses; business users only see their own.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


class Business(models.Model):
    """A tenant: one registered business on the platform."""

    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_SUSPENDED, 'Suspended'),
    ]

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=30, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='businesses_created',
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Business'
        verbose_name_plural = 'Businesses'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or 'business'
            slug = base
            n = 2
            while Business.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    def activate(self):
        self.status = self.STATUS_ACTIVE
        self.save(update_fields=['status', 'updated_at'])

    def suspend(self):
        self.status = self.STATUS_SUSPENDED
        self.save(update_fields=['status', 'updated_at'])

    @classmethod
    def get_default(cls):
        """The single tenant that owns all pre-multi-tenant data."""
        business, _ = cls.objects.get_or_create(
            slug='default',
            defaults={'name': 'Default Business'},
        )
        return business

    def admin_users(self):
        """Users whose profile belongs to this business and carry the administrator role."""
        from app.models.human_resource import UserProfile
        return settings.AUTH_USER_MODEL.objects.filter(
            profile__business=self,
            profile__roles__name__icontains='administrator',
        ).distinct()


# ---------------------------------------------------------------------------
# Scoping helpers
# ---------------------------------------------------------------------------

def user_is_platform_admin(user):
    """Platform Super Administrator: sees and manages every business."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return bool(user.profile.is_platform_admin)
    except Exception:
        return False


def current_business(user):
    """The business a user belongs to; legacy users fall back to the default business."""
    if not user or not user.is_authenticated:
        return None
    try:
        profile = user.profile
    except Exception:
        return None
    if getattr(profile, 'business_id', None):
        return profile.business
    return Business.get_default()


def business_scope(user, queryset, field='business'):
    """
    Server-side tenant scoping. Platform admins see everything; business users
    are restricted to rows whose `field` (FK name or lookup path) matches their
    business. Rows with a NULL business (platform-level rows) are visible only
    to platform admins.
    """
    if user_is_platform_admin(user):
        return queryset
    business = current_business(user)
    if business is None:
        return queryset.none()
    return queryset.filter(**{field: business})


def user_businesses(user):
    """Businesses a user may act on (all for platform admins, own business otherwise)."""
    if user_is_platform_admin(user):
        return Business.objects.all()
    business = current_business(user)
    return Business.objects.filter(pk=business.pk) if business else Business.objects.none()
