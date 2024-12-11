"""
Tests for defer() and only().
"""

from django.db import models


class Secondary(models.Model):
    first = models.CharField(max_length=50)
    second = models.CharField(max_length=50)


class Primary(models.Model):
    name = models.CharField(max_length=50)
    value = models.CharField(max_length=50)
    related = models.ForeignKey(Secondary, models.CASCADE)

    def __str__(self):
        return self.name


class PrimaryOneToOne(models.Model):
    name = models.CharField(max_length=50)
    value = models.CharField(max_length=50)
    related = models.OneToOneField(
        Secondary, models.CASCADE, related_name="primary_o2o"
    )


class Child(Primary):
    pass


class BigChild(Primary):
    other = models.CharField(max_length=50)


class ChildProxy(Child):
    class Meta:
        proxy = True


class RefreshPrimaryProxy(Primary):
    class Meta:
        proxy = True

    def refresh_from_db(self, using=None, fields=None, **kwargs):
        # Reloads all deferred fields if any of the fields is deferred.
        """
        Refresh the current instance from the database, updating its fields.

        :param using: The database alias to use for the refresh operation.
        :param fields: A list of field names to refresh from the database. If not provided, all fields will be refreshed.
        :param kwargs: Additional keyword arguments to pass to the superclass's refresh method.

        If only specific fields are requested, any deferred fields that are related to the requested fields will also be refreshed to ensure data consistency. The instance will be updated with the latest values from the database.
        """
        if fields is not None:
            fields = set(fields)
            deferred_fields = self.get_deferred_fields()
            if fields.intersection(deferred_fields):
                fields = fields.union(deferred_fields)
        super().refresh_from_db(using, fields, **kwargs)


class ShadowParent(models.Model):
    """
    ShadowParent declares a scalar, rather than a field. When this is
    overridden, the field value, rather than the scalar value must still be
    used when the field is deferred.
    """

    name = "aphrodite"


class ShadowChild(ShadowParent):
    name = models.CharField(default="adonis", max_length=6)
