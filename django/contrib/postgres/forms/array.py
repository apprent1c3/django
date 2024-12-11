import copy
from itertools import chain

from django import forms
from django.contrib.postgres.validators import (
    ArrayMaxLengthValidator,
    ArrayMinLengthValidator,
)
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from ..utils import prefix_validation_error


class SimpleArrayField(forms.CharField):
    default_error_messages = {
        "item_invalid": _("Item %(nth)s in the array did not validate:"),
    }

    def __init__(
        self, base_field, *, delimiter=",", max_length=None, min_length=None, **kwargs
    ):
        self.base_field = base_field
        self.delimiter = delimiter
        super().__init__(**kwargs)
        if min_length is not None:
            self.min_length = min_length
            self.validators.append(ArrayMinLengthValidator(int(min_length)))
        if max_length is not None:
            self.max_length = max_length
            self.validators.append(ArrayMaxLengthValidator(int(max_length)))

    def clean(self, value):
        value = super().clean(value)
        return [self.base_field.clean(val) for val in value]

    def prepare_value(self, value):
        if isinstance(value, list):
            return self.delimiter.join(
                str(self.base_field.prepare_value(v)) for v in value
            )
        return value

    def to_python(self, value):
        if isinstance(value, list):
            items = value
        elif value:
            items = value.split(self.delimiter)
        else:
            items = []
        errors = []
        values = []
        for index, item in enumerate(items):
            try:
                values.append(self.base_field.to_python(item))
            except ValidationError as error:
                errors.append(
                    prefix_validation_error(
                        error,
                        prefix=self.error_messages["item_invalid"],
                        code="item_invalid",
                        params={"nth": index + 1},
                    )
                )
        if errors:
            raise ValidationError(errors)
        return values

    def validate(self, value):
        """
        Validates a given value, checking each item against the base field.

        This method first calls the parent class's validate method to perform any 
        initial validation. It then iterates over each item in the value, attempting 
        to validate it using the base field. Any validation errors encountered are 
        collected and returned as a list of errors. If any errors are found, a 
        ValidationError is raised with the collected errors.

        Args:
            value: The value to be validated.

        Raises:
            ValidationError: If any validation errors are encountered in the items.

        """
        super().validate(value)
        errors = []
        for index, item in enumerate(value):
            try:
                self.base_field.validate(item)
            except ValidationError as error:
                errors.append(
                    prefix_validation_error(
                        error,
                        prefix=self.error_messages["item_invalid"],
                        code="item_invalid",
                        params={"nth": index + 1},
                    )
                )
        if errors:
            raise ValidationError(errors)

    def run_validators(self, value):
        super().run_validators(value)
        errors = []
        for index, item in enumerate(value):
            try:
                self.base_field.run_validators(item)
            except ValidationError as error:
                errors.append(
                    prefix_validation_error(
                        error,
                        prefix=self.error_messages["item_invalid"],
                        code="item_invalid",
                        params={"nth": index + 1},
                    )
                )
        if errors:
            raise ValidationError(errors)

    def has_changed(self, initial, data):
        try:
            value = self.to_python(data)
        except ValidationError:
            pass
        else:
            if initial in self.empty_values and value in self.empty_values:
                return False
        return super().has_changed(initial, data)


class SplitArrayWidget(forms.Widget):
    template_name = "postgres/widgets/split_array.html"

    def __init__(self, widget, size, **kwargs):
        self.widget = widget() if isinstance(widget, type) else widget
        self.size = size
        super().__init__(**kwargs)

    @property
    def is_hidden(self):
        return self.widget.is_hidden

    def value_from_datadict(self, data, files, name):
        return [
            self.widget.value_from_datadict(data, files, "%s_%s" % (name, index))
            for index in range(self.size)
        ]

    def value_omitted_from_data(self, data, files, name):
        return all(
            self.widget.value_omitted_from_data(data, files, "%s_%s" % (name, index))
            for index in range(self.size)
        )

    def id_for_label(self, id_):
        # See the comment for RadioSelect.id_for_label()
        """
        ''' 
        Generates an identifier based on the given label.

        If the input identifier is not empty, this function appends '_0' to the end of it.
        The generated identifier is then returned.

        :returns: A modified or original identifier based on the input.
        :rtype: str
        '''
        """
        if id_:
            id_ += "_0"
        return id_

    def get_context(self, name, value, attrs=None):
        """

        Get the context for rendering this widget.

        This method extends the standard context retrieval to handle a collection of subwidgets.
        It constructs a context for a group of subwidgets, each of which may have its own attributes.

        The context includes a list of subwidgets, where each subwidget's context is generated by
        calling the :meth:`get_context` method of the underlying widget. The attributes for each
        subwidget are constructed by modifying the original attributes, updating the 'id' attribute
        for each subwidget to include a unique suffix.

        The method takes into account localization settings, ensuring that the widget and its
        subwidgets are rendered accordingly.

        :param name: The name of the widget.
        :param value: The value(s) to be rendered by the widget. If the value is a list, it will be
            rendered as multiple subwidgets. If the value is not provided (or is empty), the widget
            will render an empty list of subwidgets.
        :param attrs: A dictionary of attributes to apply to the widget and its subwidgets. If not
            provided, an empty dictionary will be used.
        :return: A dictionary containing the context for rendering the widget.

        """
        attrs = {} if attrs is None else attrs
        context = super().get_context(name, value, attrs)
        if self.is_localized:
            self.widget.is_localized = self.is_localized
        value = value or []
        context["widget"]["subwidgets"] = []
        final_attrs = self.build_attrs(attrs)
        id_ = final_attrs.get("id")
        for i in range(max(len(value), self.size)):
            try:
                widget_value = value[i]
            except IndexError:
                widget_value = None
            if id_:
                final_attrs = {**final_attrs, "id": "%s_%s" % (id_, i)}
            context["widget"]["subwidgets"].append(
                self.widget.get_context(name + "_%s" % i, widget_value, final_attrs)[
                    "widget"
                ]
            )
        return context

    @property
    def media(self):
        return self.widget.media

    def __deepcopy__(self, memo):
        obj = super().__deepcopy__(memo)
        obj.widget = copy.deepcopy(self.widget)
        return obj

    @property
    def needs_multipart_form(self):
        return self.widget.needs_multipart_form


class SplitArrayField(forms.Field):
    default_error_messages = {
        "item_invalid": _("Item %(nth)s in the array did not validate:"),
    }

    def __init__(self, base_field, size, *, remove_trailing_nulls=False, **kwargs):
        self.base_field = base_field
        self.size = size
        self.remove_trailing_nulls = remove_trailing_nulls
        widget = SplitArrayWidget(widget=base_field.widget, size=size)
        kwargs.setdefault("widget", widget)
        super().__init__(**kwargs)

    def _remove_trailing_nulls(self, values):
        index = None
        if self.remove_trailing_nulls:
            for i, value in reversed(list(enumerate(values))):
                if value in self.base_field.empty_values:
                    index = i
                else:
                    break
            if index is not None:
                values = values[:index]
        return values, index

    def to_python(self, value):
        value = super().to_python(value)
        return [self.base_field.to_python(item) for item in value]

    def clean(self, value):
        cleaned_data = []
        errors = []
        if not any(value) and self.required:
            raise ValidationError(self.error_messages["required"])
        max_size = max(self.size, len(value))
        for index in range(max_size):
            item = value[index]
            try:
                cleaned_data.append(self.base_field.clean(item))
            except ValidationError as error:
                errors.append(
                    prefix_validation_error(
                        error,
                        self.error_messages["item_invalid"],
                        code="item_invalid",
                        params={"nth": index + 1},
                    )
                )
                cleaned_data.append(None)
            else:
                errors.append(None)
        cleaned_data, null_index = self._remove_trailing_nulls(cleaned_data)
        if null_index is not None:
            errors = errors[:null_index]
        errors = list(filter(None, errors))
        if errors:
            raise ValidationError(list(chain.from_iterable(errors)))
        return cleaned_data

    def has_changed(self, initial, data):
        """
        Checks if the provided data has changed from its initial state.

        This method takes into account the field's specific requirements and validation.
        It attempts to convert the data to a Python object, and if successful, removes any trailing null values.
        If both the initial and new data are considered empty, no change is detected.
        Otherwise, it delegates the change detection to the parent class's implementation.

        :param initial: The initial data to compare against.
        :param data: The new data to check for changes.
        :return: True if the data has changed, False otherwise.
        """
        try:
            data = self.to_python(data)
        except ValidationError:
            pass
        else:
            data, _ = self._remove_trailing_nulls(data)
            if initial in self.empty_values and data in self.empty_values:
                return False
        return super().has_changed(initial, data)
