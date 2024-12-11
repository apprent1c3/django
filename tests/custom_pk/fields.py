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
        """
        Checks whether the current object is equal to another object.

        This method compares the current object with another object to determine if they have the same value.
        If the other object is of the same class, it compares their `value` attributes.
        If the other object is not of the same class, it directly compares the current object's `value` with the other object.

        Returns:
            bool: True if the objects are equal, False otherwise.
        """
        if isinstance(other, self.__class__):
            return self.value == other.value
        return self.value == other


class MyWrapperField(models.CharField):
    def __init__(self, *args, **kwargs):
        """
        Initializes the class instance with the given arguments, overriding the max_length parameter to be 10, ensuring consistency across all instances.
        """
        kwargs["max_length"] = 10
        super().__init__(*args, **kwargs)

    def pre_save(self, instance, add):
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
        :param value: The value retrieved from the database.
        :param expression: The SQL expression used to retrieve the value.
        :param connection: The database connection object.
        :returns: An instance of MyWrapper wrapping the retrieved value, or None if the value is empty.
        :rtype: MyWrapper or None
        :description: This function takes a database value and wraps it in a MyWrapper object, allowing for further processing or manipulation.
                     It returns None if the value is empty, otherwise it returns the wrapped value. The function is intended to be used as part of 
                     a database interaction workflow, where it can help to transform raw database values into a more usable form.
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

        Prepare a value for use in a database query.

        This method takes a value and converts it into a format suitable for use in a database query.
        If the value is an instance of :class:`MyWrapper`, it is converted to a string representation.
        If the value is empty or :class:`None`, no value is returned.
        The method considers the current database connection and whether the value is being prepared for a query.

        :param value: The value to prepare for the database query.
        :param connection: The database connection being used.
        :param prepared: A flag indicating whether the value is being prepared for a query.
        :return: The prepared value, or :class:`None` if the input value is empty.

        """
        if not value:
            return
        if isinstance(value, MyWrapper):
            return str(value)
        return value


class MyAutoField(models.BigAutoField):
    def from_db_value(self, value, expression, connection):
        """
        Convert a database value to a wrapped object.

        This method takes a value retrieved from the database, along with the expression
        used to retrieve it and the database connection used, and returns a wrapped
        version of the value. If the value is None, None is returned instead.

        :param value: The value retrieved from the database.
        :param expression: The expression used to retrieve the value.
        :param connection: The database connection used to retrieve the value.
        :rtype: MyWrapper or None
        :return: A wrapped version of the value, or None if the value is None. 
        """
        if value is None:
            return None
        return MyWrapper(value)

    def get_prep_value(self, value):
        """
        Return the prepared value for further processing.

        This method takes a value as input, checks if it is None, and if so, returns None.
        Otherwise, it converts the value to an integer and returns the result.

        :raises ValueError: If the value cannot be converted to an integer
        :return: The prepared integer value or None if the input value is None
        :rtype: int or None
        """
        if value is None:
            return None
        return int(value)
