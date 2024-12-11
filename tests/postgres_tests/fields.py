"""
Indirection layer for PostgreSQL-specific fields, so the tests don't fail when
run with a backend other than PostgreSQL.
"""

import enum

from django.db import models

try:
    from django.contrib.postgres.fields import (
        ArrayField,
        BigIntegerRangeField,
        DateRangeField,
        DateTimeRangeField,
        DecimalRangeField,
        HStoreField,
        IntegerRangeField,
    )
    from django.contrib.postgres.search import SearchVector, SearchVectorField
except ImportError:

    class DummyArrayField(models.Field):
        def __init__(self, base_field, size=None, **kwargs):
            super().__init__(**kwargs)

        def deconstruct(self):
            """
            Deconstructs the current object into its constituent parts, inheriting behavior from the parent class.

            The deconstruction process yields the object's name, path, positional arguments, and keyword arguments. The keyword arguments are updated to include default values for the base field and size, ensuring consistency in the deconstructed representation.

            Returns:
                A tuple containing the object's name, path, positional arguments, and keyword arguments.
            """
            name, path, args, kwargs = super().deconstruct()
            kwargs.update(
                {
                    "base_field": "",
                    "size": 1,
                }
            )
            return name, path, args, kwargs

    class DummyContinuousRangeField(models.Field):
        def __init__(self, *args, default_bounds="[)", **kwargs):
            super().__init__(**kwargs)

        def deconstruct(self):
            """
            Deconstructs the object into its constituent parts for serialization or migration purposes.

            This method extends the parent class's deconstruction behavior by setting the default bounds to '[)' in the keyword arguments.

            Returns:
                tuple: A tuple containing the object's name, path, positional arguments, and keyword arguments, including the customized default bounds.
            """
            name, path, args, kwargs = super().deconstruct()
            kwargs["default_bounds"] = "[)"
            return name, path, args, kwargs

    ArrayField = DummyArrayField
    BigIntegerRangeField = models.Field
    DateRangeField = models.Field
    DateTimeRangeField = DummyContinuousRangeField
    DecimalRangeField = DummyContinuousRangeField
    HStoreField = models.Field
    IntegerRangeField = models.Field
    SearchVector = models.Expression
    SearchVectorField = models.Field


class EnumField(models.CharField):
    def get_prep_value(self, value):
        return value.value if isinstance(value, enum.Enum) else value
