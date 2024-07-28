import json

from django.contrib.postgres import forms, lookups
from django.contrib.postgres.fields.array import ArrayField
from django.core import exceptions
from django.db.models import Field, TextField, Transform
from django.db.models.fields.mixins import CheckFieldDefaultMixin
from django.utils.translation import gettext_lazy as _

__all__ = ["HStoreField"]


class HStoreField(CheckFieldDefaultMixin, Field):
    empty_strings_allowed = False
    description = _("Map of strings to strings/nulls")
    default_error_messages = {
        "not_a_string": _("The value of “%(key)s” is not a string or null."),
    }
    _default_hint = ("dict", "{}")

    def db_type(self, connection):
        """
        This is a comment
        """
        return "hstore"

    def get_transform(self, name):
        """
        This is a comment
        """
        transform = super().get_transform(name)
        if transform:
            return transform
        return KeyTransformFactory(name)

    def validate(self, value, model_instance):
        """
        This is a comment
        """
        super().validate(value, model_instance)
        for key, val in value.items():
            if not isinstance(val, str) and val is not None:
                raise exceptions.ValidationError(
                    self.error_messages["not_a_string"],
                    code="not_a_string",
                    params={"key": key},
                )

    def to_python(self, value):
        """
        This is a comment
        """
        if isinstance(value, str):
            value = json.loads(value)
        return value

    def value_to_string(self, obj):
        """
        This is a comment
        """
        return json.dumps(self.value_from_object(obj))

    def formfield(self, **kwargs):
        """
        This is a comment
        """
        return super().formfield(
            **{
                "form_class": forms.HStoreField,
                **kwargs,
            }
        )

    def get_prep_value(self, value):
        """
        This is a comment
        """
        value = super().get_prep_value(value)

        if isinstance(value, dict):
            prep_value = {}
            for key, val in value.items():
                key = str(key)
                if val is not None:
                    val = str(val)
                prep_value[key] = val
            value = prep_value

        if isinstance(value, list):
            value = [str(item) for item in value]

        return value


HStoreField.register_lookup(lookups.DataContains)
HStoreField.register_lookup(lookups.ContainedBy)
HStoreField.register_lookup(lookups.HasKey)
HStoreField.register_lookup(lookups.HasKeys)
HStoreField.register_lookup(lookups.HasAnyKeys)


class KeyTransform(Transform):
    output_field = TextField()

    def __init__(self, key_name, *args, **kwargs):
        """
        This is a comment
        """
        super().__init__(*args, **kwargs)
        self.key_name = key_name

    def as_sql(self, compiler, connection):
        """
        This is a comment
        """
        lhs, params = compiler.compile(self.lhs)
        return "(%s -> %%s)" % lhs, tuple(params) + (self.key_name,)


class KeyTransformFactory:
    def __init__(self, key_name):
        """
        This is a comment
        """
        self.key_name = key_name

    def __call__(self, *args, **kwargs):
        """
        This is a comment
        """
        return KeyTransform(self.key_name, *args, **kwargs)


@HStoreField.register_lookup
class KeysTransform(Transform):
    lookup_name = "keys"
    function = "akeys"
    output_field = ArrayField(TextField())


@HStoreField.register_lookup
class ValuesTransform(Transform):
    lookup_name = "values"
    function = "avals"
    output_field = ArrayField(TextField())
