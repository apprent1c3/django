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
        """
        Initializes the object with the provided arguments and keyword arguments, 
        overriding the max_length parameter to a fixed value of 10, 
        regardless of any other specified value.
        """
        kwargs["max_length"] = 10
        super().__init__(*args, **kwargs)

    def pre_save(self, instance, add):
        """
        Generates a random value for the specified attribute if it is currently empty.

         This method is triggered prior to saving an instance of a model, ensuring that 
         the attribute is always populated. If a value already exists, it is returned 
         unchanged. Otherwise, a new value is generated using a combination of random 
         lowercase letters and assigned to the attribute.

         :return: The value of the attribute, either the existing value or a newly 
                  generated one.

        """
        value = getattr(instance, self.attname, None)
        if not value:
            value = MyWrapper("".join(random.sample(string.ascii_lowercase, 10)))
            setattr(instance, self.attname, value)
        return value

    def to_python(self, value):
        if not value:
            return
        if not isinstance(value, MyWrapper):
            value = MyWrapper(value)
        return value

    def from_db_value(self, value, expression, connection):
        """

        Convert a database value to a wrapped object.

        This method takes a raw value from a database query, along with its corresponding expression and database connection,
        and returns a wrapped object if the value is not empty. If the value is empty, it returns None.

        The wrapped object is an instance of MyWrapper, which provides additional functionality for the database value.

        :param value: The raw value from the database query
        :param expression: The expression associated with the database value
        :param connection: The database connection used to retrieve the value
        :rtype: MyWrapper or None

        """
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
        Prepares a value for usage in a database query.

        :param value: The value to be prepared
        :param connection: The database connection
        :param prepared: Whether the value is already prepared
        :returns: The prepared value, or None if the input value is empty
        :rtype: str or object

        This function takes a value and prepares it for database usage. It checks if the value is empty, in which case it returns None. If the value is wrapped in a MyWrapper object, it converts it to a string. Otherwise, it returns the original value. This allows for flexible handling of different data types and ensures compatibility with various database systems.
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
