import copy
import datetime

from django.contrib.auth.models import User
from django.db import models


class RevisionableModel(models.Model):
    base = models.ForeignKey("self", models.SET_NULL, null=True)
    title = models.CharField(blank=True, max_length=255)
    when = models.DateTimeField(default=datetime.datetime.now)

    def save(self, *args, force_insert=False, force_update=False, **kwargs):
        """
        Saves the current object instance to the database.

        This method overrides the default save behavior to handle a specific case where the object's base attribute is not set.
        When the base attribute is empty, it sets the base attribute to the current object instance and then saves the object again
        to ensure the base attribute is persisted to the database.

        Parameters
        ----------
        *args
            Variable length non-keyword arguments.
        force_insert : bool, optional
            Forces the object to be inserted as a new record, rather than updating an existing one (default is False).
        force_update : bool, optional
            Forces the object to be updated, rather than inserting a new record (default is False).
        **kwargs
            Variable length keyword arguments.

        Note
        ----
        The actual saving of the object is delegated to the superclass's save method, which handles the underlying database operation.
        This method provides an additional layer of logic to handle the special case of an unset base attribute.

        """
        super().save(
            *args, force_insert=force_insert, force_update=force_update, **kwargs
        )
        if not self.base:
            self.base = self
            super().save(*args, **kwargs)

    def new_revision(self):
        new_revision = copy.copy(self)
        new_revision.pk = None
        return new_revision


class Order(models.Model):
    created_by = models.ForeignKey(User, models.CASCADE)
    text = models.TextField()


class TestObject(models.Model):
    first = models.CharField(max_length=20)
    second = models.CharField(max_length=20)
    third = models.CharField(max_length=20)

    def __str__(self):
        return "TestObject: %s,%s,%s" % (self.first, self.second, self.third)
