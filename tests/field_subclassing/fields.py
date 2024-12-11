from django.db import models
from django.db.models.query_utils import DeferredAttribute


class CustomTypedField(models.TextField):
    def db_type(self, connection):
        return "custom_field"


class CustomDeferredAttribute(DeferredAttribute):
    def __get__(self, instance, cls=None):
        """
        Special method to implement descriptor protocol for getting attribute values.

        Invokes the original getter method provided by the superclass, but also tracks the 
        number of times the attribute is accessed for the given instance. This allows for 
        monitoring and logging of attribute access patterns.

        :param instance: The instance for which the attribute is being accessed.
        :param cls: The class of the instance, defaults to None.
        :return: The value of the attribute being accessed.

        """
        self._count_call(instance, "get")
        return super().__get__(instance, cls)

    def __set__(self, instance, value):
        self._count_call(instance, "set")
        instance.__dict__[self.field.attname] = value

    def _count_call(self, instance, get_or_set):
        """
        Increments the call count for a specific field and operation type on a given instance.

        This function keeps track of the number of times a field's getter or setter is called.
        It uses an internal attribute on the instance to store the count, and the attribute name
        is generated based on the field's name and the operation type (get or set). The count
        is incremented by 1 each time the function is called.

        :param instance: The instance for which to increment the call count
        :param get_or_set: The type of operation being performed (either 'get' or 'set')

        """
        count_attr = "_%s_%s_count" % (self.field.attname, get_or_set)
        count = getattr(instance, count_attr, 0)
        setattr(instance, count_attr, count + 1)


class CustomDescriptorField(models.CharField):
    descriptor_class = CustomDeferredAttribute
