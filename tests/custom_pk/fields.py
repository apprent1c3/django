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
        Automatically generates and assigns a unique value to the attribute specified by `self.attname` if it is empty, ensuring it is populated before saving the instance.
        """
        value = getattr(instance, self.attname, None)
        if not value:
            value = MyWrapper("".join(random.sample(string.ascii_lowercase, 10)))
            setattr(instance, self.attname, value)
        return value

    def to_python(self, value):
        """
        Ensures the provided value is wrapped in a :class:`MyWrapper` instance, returning the wrapped value or None if the input value is empty.
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
        Prepares a database value for saving by converting it to a string if it's an instance of MyWrapper, or returning the original value otherwise. Returns None if the value is empty.
        """
        if not value:
            return
        if isinstance(value, MyWrapper):
            return str(value)
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        """
        Returns a database-prepared value, converting wrapped values to strings if necessary.
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
