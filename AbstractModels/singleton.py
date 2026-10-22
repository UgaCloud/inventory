from django.db import models


class SingletonModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        """
        Return the one and only row of this singleton, creating it if needed.

        The row is bootstrapped automatically the first time any page is
        rendered. That is an internal side effect of reading the settings,
        not a user action, so it is flagged with ``_audit_skip`` to keep it
        out of the audit trail.
        """
        obj = cls.objects.filter(pk=1).first()
        if obj is None:
            obj = cls(pk=1)
            obj._audit_skip = True
            obj.save()
        return obj
