"""
Per-user preferences.

The settings workspace keeps the personal choices of a user (appearance,
which events raise a notification) apart from the company wide organisation
settings, which live in ``app.models.organization``.
"""
from django.conf import settings
from django.db import models


class UserPreference(models.Model):
    """Personal settings of one user."""

    THEME_CHOICES = [
        ('system', 'Match my system'),
        ('light', 'Light'),
        ('dark', 'Dark'),
    ]
    DENSITY_CHOICES = [
        ('comfortable', 'Comfortable'),
        ('compact', 'Compact'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    theme = models.CharField(max_length=16, choices=THEME_CHOICES, default='system')
    density = models.CharField(max_length=16, choices=DENSITY_CHOICES, default='comfortable')
    sidebar_collapsed = models.BooleanField(default=False)

    # Which events raise a notification for this user.
    notify_sales = models.BooleanField(default=True)
    notify_purchasing = models.BooleanField(default=True)
    notify_low_stock = models.BooleanField(default=True)
    notify_transfers = models.BooleanField(default=True)
    notify_roles = models.BooleanField(default=True)
    notify_business = models.BooleanField(default=True)
    digest_email = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User preference'
        verbose_name_plural = 'User preferences'

    def __str__(self):
        return f'Preferences of {self.user}'

    @classmethod
    def for_user(cls, user):
        """The preferences of a user, created on first access."""
        preference, _ = cls.objects.get_or_create(user=user)
        return preference
