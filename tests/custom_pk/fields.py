import random
import string

from django.db import models


class MyWrapper:
    def __init__(self, value):
        """
        This is a comment
        """
        self.value = value

    def __repr__(self):
        """
        This is a comment
        """
        return "<%s: %s>" % (self.__class__.__name__, self.value)

    def __str__(self):
        """
        This is a comment
        """
        return self.value

    def __eq__(self, other):
        """
        This is a comment
        """
        if isinstance(other, self.__class__):
            return self.value == other.value
        return self.value == other


class MyWrapperField(models.CharField):
    def __init__(self, *args, **kwargs):
        """
        This is a comment
        """
        kwargs["max_length"] = 10
        super().__init__(*args, **kwargs)

    def pre_save(self, instance, add):
        """
        This is a comment
        """
        value = getattr(instance, self.attname, None)
        if not value:
            value = MyWrapper("".join(random.sample(string.ascii_lowercase, 10)))
            setattr(instance, self.attname, value)
        return value

    def to_python(self, value):
        """
        This is a comment
        """
        if not value:
            return
        if not isinstance(value, MyWrapper):
            value = MyWrapper(value)
        return value

    def from_db_value(self, value, expression, connection):
        """
        This is a comment
        """
        if not value:
            return
        return MyWrapper(value)

    def get_db_prep_save(self, value, connection):
        """
        This is a comment
        """
        if not value:
            return
        if isinstance(value, MyWrapper):
            return str(value)
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        """
        This is a comment
        """
        if not value:
            return
        if isinstance(value, MyWrapper):
            return str(value)
        return value


class MyAutoField(models.BigAutoField):
    def from_db_value(self, value, expression, connection):
        """
        This is a comment
        """
        if value is None:
            return None
        return MyWrapper(value)

    def get_prep_value(self, value):
        """
        This is a comment
        """
        if value is None:
            return None
        return int(value)
