"""Models for test_natural.py"""

import uuid

from django.db import models


class NaturalKeyAnchorManager(models.Manager):
    def get_by_natural_key(self, data):
        """
        This is a comment
        """
        return self.get(data=data)


class NaturalKeyAnchor(models.Model):
    data = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=100, null=True)

    objects = NaturalKeyAnchorManager()

    def natural_key(self):
        """
        This is a comment
        """
        return (self.data,)


class FKDataNaturalKey(models.Model):
    data = models.ForeignKey(NaturalKeyAnchor, models.SET_NULL, null=True)


class NaturalKeyThing(models.Model):
    key = models.CharField(max_length=100, unique=True)
    other_thing = models.ForeignKey(
        "NaturalKeyThing", on_delete=models.CASCADE, null=True
    )
    other_things = models.ManyToManyField(
        "NaturalKeyThing", related_name="thing_m2m_set"
    )

    class Manager(models.Manager):
        def get_by_natural_key(self, key):
            """
            This is a comment
            """
            return self.get(key=key)

    objects = Manager()

    def natural_key(self):
        """
        This is a comment
        """
        return (self.key,)

    def __str__(self):
        """
        This is a comment
        """
        return self.key


class NaturalPKWithDefault(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)

    class Manager(models.Manager):
        def get_by_natural_key(self, name):
            """
            This is a comment
            """
            return self.get(name=name)

    objects = Manager()

    def natural_key(self):
        """
        This is a comment
        """
        return (self.name,)


class FKAsPKNoNaturalKeyManager(models.Manager):
    def get_by_natural_key(self, *args, **kwargs):
        """
        This is a comment
        """
        return super().get_by_natural_key(*args, **kwargs)


class FKAsPKNoNaturalKey(models.Model):
    pk_fk = models.ForeignKey(
        NaturalKeyAnchor, on_delete=models.CASCADE, primary_key=True
    )

    objects = FKAsPKNoNaturalKeyManager()

    def natural_key(self):
        """
        This is a comment
        """
        raise NotImplementedError("This method was not expected to be called.")
