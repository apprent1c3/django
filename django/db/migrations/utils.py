import datetime
import re
from collections import namedtuple

from django.db.models.fields.related import RECURSIVE_RELATIONSHIP_CONSTANT

FieldReference = namedtuple("FieldReference", "to through")

COMPILED_REGEX_TYPE = type(re.compile(""))


class RegexObject:
    def __init__(self, obj):
        self.pattern = obj.pattern
        self.flags = obj.flags

    def __eq__(self, other):
        if not isinstance(other, RegexObject):
            return NotImplemented
        return self.pattern == other.pattern and self.flags == other.flags


def get_migration_name_timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M")


def resolve_relation(model, app_label=None, model_name=None):
    """
    Resolves a model relationship given a model class or model reference string.

    The function takes into account recursive and unscoped relationships by utilizing the provided app_label and model_name to determine the scope. Returns a tuple containing the app label and model name.
    """
    if isinstance(model, str):
        if model == RECURSIVE_RELATIONSHIP_CONSTANT:
            if app_label is None or model_name is None:
                raise TypeError(
                    "app_label and model_name must be provided to resolve "
                    "recursive relationships."
                )
            return app_label, model_name
        if "." in model:
            app_label, model_name = model.split(".", 1)
            return app_label, model_name.lower()
        if app_label is None:
            raise TypeError(
                "app_label must be provided to resolve unscoped model relationships."
            )
        return app_label, model.lower()
    return model._meta.app_label, model._meta.model_name


def field_references(
    model_tuple,
    field,
    reference_model_tuple,
    reference_field_name=None,
    reference_field=None,
):
    """
    Determines whether a given field in a model references another model.

    This function checks if a `field` in a `model_tuple` has a relation to a `reference_model_tuple`. 
    It returns a `FieldReference` object if a relation is found, or `False` otherwise.
    Note that using `reference_field_name` without providing `reference_field` may lead to false positives due to introspection limitations.
    """
    remote_field = field.remote_field
    if not remote_field:
        return False
    references_to = None
    references_through = None
    if resolve_relation(remote_field.model, *model_tuple) == reference_model_tuple:
        to_fields = getattr(field, "to_fields", None)
        if (
            reference_field_name is None
            or
            # Unspecified to_field(s).
            to_fields is None
            or
            # Reference to primary key.
            (
                None in to_fields
                and (reference_field is None or reference_field.primary_key)
            )
            or
            # Reference to field.
            reference_field_name in to_fields
        ):
            references_to = (remote_field, to_fields)
    through = getattr(remote_field, "through", None)
    if through and resolve_relation(through, *model_tuple) == reference_model_tuple:
        through_fields = remote_field.through_fields
        if (
            reference_field_name is None
            or
            # Unspecified through_fields.
            through_fields is None
            or
            # Reference to field.
            reference_field_name in through_fields
        ):
            references_through = (remote_field, through_fields)
    if not (references_to or references_through):
        return False
    return FieldReference(references_to, references_through)


def get_references(state, model_tuple, field_tuple=()):
    """
    Generates references to a specific model and field within the provided state context.

     Everywhere field_tuple is provided, it restricts the references to a given field of model_tuple.
    """
    for state_model_tuple, model_state in state.models.items():
        for name, field in model_state.fields.items():
            reference = field_references(
                state_model_tuple, field, model_tuple, *field_tuple
            )
            if reference:
                yield model_state, name, field, reference


def field_is_referenced(state, model_tuple, field_tuple):
    """Return whether `field_tuple` is referenced by any state models."""
    return next(get_references(state, model_tuple, field_tuple), None) is not None
