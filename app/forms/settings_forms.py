"""
Forms of the settings workspace.
"""
from django import forms

from app.models.preferences import UserPreference


class AppearancePreferenceForm(forms.ModelForm):
    """How the interface looks for one user."""

    class Meta:
        model = UserPreference
        fields = ('theme', 'density', 'sidebar_collapsed')
        widgets = {
            'sidebar_collapsed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class NotificationPreferenceForm(forms.ModelForm):
    """Which events raise a notification for one user."""

    class Meta:
        model = UserPreference
        fields = (
            'notify_sales',
            'notify_purchasing',
            'notify_low_stock',
            'notify_transfers',
            'notify_roles',
            'notify_business',
            'digest_email',
        )
        widgets = {
            name: forms.CheckboxInput(attrs={'class': 'form-check-input'})
            for name in (
                'notify_sales', 'notify_purchasing', 'notify_low_stock',
                'notify_transfers', 'notify_roles', 'notify_business',
                'digest_email',
            )
        }
