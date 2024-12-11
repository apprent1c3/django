import json

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

__all__ = ["HStoreField"]


class HStoreField(forms.CharField):
    """
    A field for HStore data which accepts dictionary JSON input.
    """

    widget = forms.Textarea
    default_error_messages = {
        "invalid_json": _("Could not load JSON data."),
        "invalid_format": _("Input must be a JSON dictionary."),
    }

    def prepare_value(self, value):
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return value

    def to_python(self, value):
        """

        Converts a given value to a Python dictionary.

        This function takes a value, which can be either a dictionary, a JSON string, or None,
        and converts it into a Python dictionary. If the value is None, an empty dictionary is
        returned. If the value is not a dictionary, it attempts to parse it as a JSON string.
        If the parsing fails or the resulting value is not a dictionary, a ValidationError is raised.

        The resulting dictionary will have all non-null values converted to strings.

        Args:
            value: The value to convert to a dictionary.

        Returns:
            A dictionary representation of the input value.

        Raises:
            ValidationError: If the input value cannot be converted to a dictionary.

        """
        if not value:
            return {}
        if not isinstance(value, dict):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise ValidationError(
                    self.error_messages["invalid_json"],
                    code="invalid_json",
                )

        if not isinstance(value, dict):
            raise ValidationError(
                self.error_messages["invalid_format"],
                code="invalid_format",
            )

        # Cast everything to strings for ease.
        for key, val in value.items():
            if val is not None:
                val = str(val)
            value[key] = val
        return value

    def has_changed(self, initial, data):
        """
        Return True if data differs from initial.
        """
        # For purposes of seeing whether something has changed, None is
        # the same as an empty dict, if the data or initial value we get
        # is None, replace it w/ {}.
        initial_value = self.to_python(initial)
        return super().has_changed(initial_value, data)
