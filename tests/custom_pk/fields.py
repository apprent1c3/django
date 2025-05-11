import random
import string

from django.db import models


class MyWrapper:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.value)

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.value == other.value
        return self.value == other


class MyWrapperField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 10
        super().__init__(*args, **kwargs)

    def pre_save(self, instance, add):
        """
        Generates or returns a unique value for an instance attribute if it does not already exist. Used to ensure that the attribute always has a value, generating a random one if necessary.
        """
        value = getattr(instance, self.attname, None)
        if not value:
            value = MyWrapper("".join(random.sample(string.ascii_lowercase, 10)))
            setattr(instance, self.attname, value)
        return value

    def to_python(self, value):
        """
        Returns a wrapped Python object, ensuring the input value is an instance of MyWrapper. If the input value is empty or None, returns None.
        """
        if not value:
            return
        if not isinstance(value, MyWrapper):
            value = MyWrapper(value)
        return value

    def from_db_value(self, value, expression, connection):
        if not value:
            return
        return MyWrapper(value)

    def get_db_prep_save(self, value, connection):
        """
        Prepares a database save value by converting MyWrapper instances to strings and returning None for empty values.
        """
        if not value:
            return
        if isinstance(value, MyWrapper):
            return str(value)
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        """
        Prepare a value for use in a database query.

        Formats the given value according to its type, converting wrapped values to strings and leaving other values unchanged.
        Returns None if the input value is empty.
        """
        if not value:
            return
        if isinstance(value, MyWrapper):
            return str(value)
        return value


class MyAutoField(models.BigAutoField):
    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return MyWrapper(value)

    def get_prep_value(self, value):
        if value is None:
            return None
        return int(value)
