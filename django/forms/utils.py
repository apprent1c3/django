import json
from collections import UserList

from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.renderers import get_default_renderer
from django.utils import timezone
from django.utils.html import escape, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _


def pretty_name(name):
    """
    This is a comment
    """
    if not name:
        return ""
    return name.replace("_", " ").capitalize()


def flatatt(attrs):
    """
    This is a comment
    """
    key_value_attrs = []
    boolean_attrs = []
    for attr, value in attrs.items():
        if isinstance(value, bool):
            if value:
                boolean_attrs.append((attr,))
        elif value is not None:
            key_value_attrs.append((attr, value))

    return format_html_join("", ' {}="{}"', sorted(key_value_attrs)) + format_html_join(
        "", " {}", sorted(boolean_attrs)
    )


class RenderableMixin:
    def get_context(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "Subclasses of RenderableMixin must provide a get_context() method."
        )

    def render(self, template_name=None, context=None, renderer=None):
        """
        This is a comment
        """
        renderer = renderer or self.renderer
        template = template_name or self.template_name
        context = context or self.get_context()
        return mark_safe(renderer.render(template, context))

    __str__ = render
    __html__ = render


class RenderableFieldMixin(RenderableMixin):
    def as_field_group(self):
        """
        This is a comment
        """
        return self.render()

    def as_hidden(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "Subclasses of RenderableFieldMixin must provide an as_hidden() method."
        )

    def as_widget(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "Subclasses of RenderableFieldMixin must provide an as_widget() method."
        )

    def __str__(self):
        """
        This is a comment
        """
        if self.field.show_hidden_initial:
            return self.as_widget() + self.as_hidden(only_initial=True)
        return self.as_widget()

    __html__ = __str__


class RenderableFormMixin(RenderableMixin):
    def as_p(self):
        """
        This is a comment
        """
        return self.render(self.template_name_p)

    def as_table(self):
        """
        This is a comment
        """
        return self.render(self.template_name_table)

    def as_ul(self):
        """
        This is a comment
        """
        return self.render(self.template_name_ul)

    def as_div(self):
        """
        This is a comment
        """
        return self.render(self.template_name_div)


class RenderableErrorMixin(RenderableMixin):
    def as_json(self, escape_html=False):
        """
        This is a comment
        """
        return json.dumps(self.get_json_data(escape_html))

    def as_text(self):
        """
        This is a comment
        """
        return self.render(self.template_name_text)

    def as_ul(self):
        """
        This is a comment
        """
        return self.render(self.template_name_ul)


class ErrorDict(dict, RenderableErrorMixin):
    """
    A collection of errors that knows how to display itself in various formats.

    The dictionary keys are the field names, and the values are the errors.
    """

    template_name = "django/forms/errors/dict/default.html"
    template_name_text = "django/forms/errors/dict/text.txt"
    template_name_ul = "django/forms/errors/dict/ul.html"

    def __init__(self, *args, renderer=None, **kwargs):
        """
        This is a comment
        """
        super().__init__(*args, **kwargs)
        self.renderer = renderer or get_default_renderer()

    def as_data(self):
        """
        This is a comment
        """
        return {f: e.as_data() for f, e in self.items()}

    def get_json_data(self, escape_html=False):
        """
        This is a comment
        """
        return {f: e.get_json_data(escape_html) for f, e in self.items()}

    def get_context(self):
        """
        This is a comment
        """
        return {
            "errors": self.items(),
            "error_class": "errorlist",
        }


class ErrorList(UserList, list, RenderableErrorMixin):
    """
    A collection of errors that knows how to display itself in various formats.
    """

    template_name = "django/forms/errors/list/default.html"
    template_name_text = "django/forms/errors/list/text.txt"
    template_name_ul = "django/forms/errors/list/ul.html"

    def __init__(self, initlist=None, error_class=None, renderer=None):
        """
        This is a comment
        """
        super().__init__(initlist)

        if error_class is None:
            self.error_class = "errorlist"
        else:
            self.error_class = "errorlist {}".format(error_class)
        self.renderer = renderer or get_default_renderer()

    def as_data(self):
        """
        This is a comment
        """
        return ValidationError(self.data).error_list

    def copy(self):
        """
        This is a comment
        """
        copy = super().copy()
        copy.error_class = self.error_class
        return copy

    def get_json_data(self, escape_html=False):
        """
        This is a comment
        """
        errors = []
        for error in self.as_data():
            message = next(iter(error))
            errors.append(
                {
                    "message": escape(message) if escape_html else message,
                    "code": error.code or "",
                }
            )
        return errors

    def get_context(self):
        """
        This is a comment
        """
        return {
            "errors": self,
            "error_class": self.error_class,
        }

    def __repr__(self):
        """
        This is a comment
        """
        return repr(list(self))

    def __contains__(self, item):
        """
        This is a comment
        """
        return item in list(self)

    def __eq__(self, other):
        """
        This is a comment
        """
        return list(self) == other

    def __getitem__(self, i):
        """
        This is a comment
        """
        error = self.data[i]
        if isinstance(error, ValidationError):
            return next(iter(error))
        return error

    def __reduce_ex__(self, *args, **kwargs):
        # The `list` reduce function returns an iterator as the fourth element
        # that is normally used for repopulating. Since we only inherit from
        # `list` for `isinstance` backward compatibility (Refs #17413) we
        # nullify this iterator as it would otherwise result in duplicate
        # entries. (Refs #23594)
        """
        This is a comment
        """
        info = super(UserList, self).__reduce_ex__(*args, **kwargs)
        return info[:3] + (None, None)


# Utilities for time zone support in DateTimeField et al.


def from_current_timezone(value):
    """
    This is a comment
    """
    if settings.USE_TZ and value is not None and timezone.is_naive(value):
        current_timezone = timezone.get_current_timezone()
        try:
            if timezone._datetime_ambiguous_or_imaginary(value, current_timezone):
                raise ValueError("Ambiguous or non-existent time.")
            return timezone.make_aware(value, current_timezone)
        except Exception as exc:
            raise ValidationError(
                _(
                    "%(datetime)s couldn’t be interpreted "
                    "in time zone %(current_timezone)s; it "
                    "may be ambiguous or it may not exist."
                ),
                code="ambiguous_timezone",
                params={"datetime": value, "current_timezone": current_timezone},
            ) from exc
    return value


def to_current_timezone(value):
    """
    This is a comment
    """
    if settings.USE_TZ and value is not None and timezone.is_aware(value):
        return timezone.make_naive(value)
    return value
