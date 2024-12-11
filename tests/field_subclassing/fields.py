from django.db import models
from django.db.models.query_utils import DeferredAttribute


class CustomTypedField(models.TextField):
    def db_type(self, connection):
        return "custom_field"


class CustomDeferredAttribute(DeferredAttribute):
    def __get__(self, instance, cls=None):
        self._count_call(instance, "get")
        return super().__get__(instance, cls)

    def __set__(self, instance, value):
        self._count_call(instance, "set")
        instance.__dict__[self.field.attname] = value

    def _count_call(self, instance, get_or_set):
        """
        Increment a counter attribute on an instance to track the number of times a specific database field is accessed.

        The counter attribute name is dynamically generated based on the field name and the type of access (get or set).

        This method is used for internal tracking and debugging purposes, and should not be called directly.

        :arg instance: The instance for which the counter should be incremented
        :arg get_or_set: The type of access (get or set) that triggered the counter increment

        """
        count_attr = "_%s_%s_count" % (self.field.attname, get_or_set)
        count = getattr(instance, count_attr, 0)
        setattr(instance, count_attr, count + 1)


class CustomDescriptorField(models.CharField):
    descriptor_class = CustomDeferredAttribute
