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
        value = getattr(instance, self.attname, None)
        if not value:
            value = MyWrapper("".join(random.sample(string.ascii_lowercase, 10)))
            setattr(instance, self.attname, value)
        return value

    def to_python(self, value):
        """
        Converts a value to a Python-compatible format.

        This method takes an input value and ensures it is wrapped in a :class:`MyWrapper` object,
        which provides a standardized interface for Python interactions.

        If the input value is empty or already an instance of :class:`MyWrapper`, this method
        will either return nothing or the original value, respectively.

        The returned value can be safely used in Python contexts, with the wrapper providing
        any necessary adapter logic to facilitate seamless integration.

        :returns: The wrapped input value, or None if the input value is empty.
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
        if not value:
            return
        if isinstance(value, MyWrapper):
            return str(value)
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        """
        Return a value prepared for database insertion.

        This method takes an input value and prepares it for use in a database query.
        It handles a specific type of wrapper object, converting it to a string representation.
        If the input value is empty or None, this method returns None.
        Otherwise, it returns the input value with any necessary transformations applied.

        :param value: The value to be prepared for database insertion
        :param connection: The database connection being used
        :param prepared: A flag indicating whether the value is already prepared
        :return: The prepared value, or None if the input value is empty
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
