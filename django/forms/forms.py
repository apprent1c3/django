"""
Form classes
"""

import copy
import datetime

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.forms.fields import Field
from django.forms.utils import ErrorDict, ErrorList, RenderableFormMixin
from django.forms.widgets import Media, MediaDefiningClass
from django.utils.datastructures import MultiValueDict
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from .renderers import get_default_renderer

__all__ = ("BaseForm", "Form")


class DeclarativeFieldsMetaclass(MediaDefiningClass):
    """Collect Fields declared on the base classes."""

    def __new__(mcs, name, bases, attrs):
        # Collect fields from current class and remove them from attrs.
        """
        Creates a new class, collecting and processing field definitions from the class and its bases.

        Automatically identifies and separates Field instances from other class attributes, 
        and constructs a comprehensive mapping of fields, including those defined in parent classes.

        Resulting class has `base_fields` and `declared_fields` attributes, both referencing the 
        collected fields, with overrides from parent classes properly handled.
        """
        attrs["declared_fields"] = {
            key: attrs.pop(key)
            for key, value in list(attrs.items())
            if isinstance(value, Field)
        }

        new_class = super().__new__(mcs, name, bases, attrs)

        # Walk through the MRO.
        declared_fields = {}
        for base in reversed(new_class.__mro__):
            # Collect fields from base class.
            if hasattr(base, "declared_fields"):
                declared_fields.update(base.declared_fields)

            # Field shadowing.
            for attr, value in base.__dict__.items():
                if value is None and attr in declared_fields:
                    declared_fields.pop(attr)

        new_class.base_fields = declared_fields
        new_class.declared_fields = declared_fields

        return new_class


class BaseForm(RenderableFormMixin):
    """
    The main implementation of all the Form logic. Note that this class is
    different than Form. See the comments by the Form class for more info. Any
    improvements to the form API should be made to this class, not to the Form
    class.
    """

    default_renderer = None
    field_order = None
    prefix = None
    use_required_attribute = True

    template_name_div = "django/forms/div.html"
    template_name_p = "django/forms/p.html"
    template_name_table = "django/forms/table.html"
    template_name_ul = "django/forms/ul.html"
    template_name_label = "django/forms/label.html"

    def __init__(
        self,
        data=None,
        files=None,
        auto_id="id_%s",
        prefix=None,
        initial=None,
        error_class=ErrorList,
        label_suffix=None,
        empty_permitted=False,
        field_order=None,
        use_required_attribute=None,
        renderer=None,
    ):
        """
        Initialize a form instance with optional data and configuration.

        :param data: Data to initialize the form with (defaults to None)
        :param files: Files to initialize the form with (defaults to None)
        :param auto_id: Auto ID prefix (defaults to 'id_%s')
        :param prefix: Prefix for form fields (defaults to None)
        :param initial: Initial values for form fields (defaults to None)
        :param error_class: Error class for form validation (defaults to ErrorList)
        :param label_suffix: Suffix for form field labels (defaults to ':')
        :param empty_permitted: Allow empty forms (defaults to False)
        :param field_order: Order of form fields (defaults to None)
        :param use_required_attribute: Use required attribute for form fields (defaults to None)
        :param renderer: Form renderer (defaults to None)

        This method sets up the form instance with the provided data and configuration, 
        including auto ID generation, error handling, and field ordering.
        """
        self.is_bound = data is not None or files is not None
        self.data = MultiValueDict() if data is None else data
        self.files = MultiValueDict() if files is None else files
        self.auto_id = auto_id
        if prefix is not None:
            self.prefix = prefix
        self.initial = initial or {}
        self.error_class = error_class
        # Translators: This is the default suffix added to form field labels
        self.label_suffix = label_suffix if label_suffix is not None else _(":")
        self.empty_permitted = empty_permitted
        self._errors = None  # Stores the errors after clean() has been called.

        # The base_fields class attribute is the *class-wide* definition of
        # fields. Because a particular *instance* of the class might want to
        # alter self.fields, we create self.fields here by copying base_fields.
        # Instances should always modify self.fields; they should not modify
        # self.base_fields.
        self.fields = copy.deepcopy(self.base_fields)
        self._bound_fields_cache = {}
        self.order_fields(self.field_order if field_order is None else field_order)

        if use_required_attribute is not None:
            self.use_required_attribute = use_required_attribute

        if self.empty_permitted and self.use_required_attribute:
            raise ValueError(
                "The empty_permitted and use_required_attribute arguments may "
                "not both be True."
            )

        # Initialize form renderer. Use a global default if not specified
        # either as an argument or as self.default_renderer.
        if renderer is None:
            if self.default_renderer is None:
                renderer = get_default_renderer()
            else:
                renderer = self.default_renderer
                if isinstance(self.default_renderer, type):
                    renderer = renderer()
        self.renderer = renderer

    def order_fields(self, field_order):
        """
        Rearrange the fields according to the specified order, allowing for backward compatibility and field disabling.
        """
        if field_order is None:
            return
        fields = {}
        for key in field_order:
            try:
                fields[key] = self.fields.pop(key)
            except KeyError:  # ignore unknown fields
                pass
        fields.update(self.fields)  # add remaining fields in original order
        self.fields = fields

    def __repr__(self):
        """
        Returns a string representation of the object, including its bound state, validity status, and a list of fields. The validity status is 'Unknown' if errors have not been checked, otherwise it indicates whether the object is bound and has no errors.
        """
        if self._errors is None:
            is_valid = "Unknown"
        else:
            is_valid = self.is_bound and not self._errors
        return "<%(cls)s bound=%(bound)s, valid=%(valid)s, fields=(%(fields)s)>" % {
            "cls": self.__class__.__name__,
            "bound": self.is_bound,
            "valid": is_valid,
            "fields": ";".join(self.fields),
        }

    def _bound_items(self):
        """Yield (name, bf) pairs, where bf is a BoundField object."""
        for name in self.fields:
            yield name, self[name]

    def __iter__(self):
        """Yield the form's fields as BoundField objects."""
        for name in self.fields:
            yield self[name]

    def __getitem__(self, name):
        """
        Retrieves a BoundField instance associated with the given name, allowing access to form fields by their names. Raises a KeyError if the specified field does not exist.
        """
        try:
            field = self.fields[name]
        except KeyError:
            raise KeyError(
                "Key '%s' not found in '%s'. Choices are: %s."
                % (
                    name,
                    self.__class__.__name__,
                    ", ".join(sorted(self.fields)),
                )
            )
        if name not in self._bound_fields_cache:
            self._bound_fields_cache[name] = field.get_bound_field(self, name)
        return self._bound_fields_cache[name]

    @property
    def errors(self):
        """Return an ErrorDict for the data provided for the form."""
        if self._errors is None:
            self.full_clean()
        return self._errors

    def is_valid(self):
        """Return True if the form has no errors, or False otherwise."""
        return self.is_bound and not self.errors

    def add_prefix(self, field_name):
        """
        Return the field name with a prefix appended, if this Form has a
        prefix set.

        Subclasses may wish to override.
        """
        return "%s-%s" % (self.prefix, field_name) if self.prefix else field_name

    def add_initial_prefix(self, field_name):
        """Add an 'initial' prefix for checking dynamic initial values."""
        return "initial-%s" % self.add_prefix(field_name)

    def _widget_data_value(self, widget, html_name):
        # value_from_datadict() gets the data from the data dictionaries.
        # Each widget type knows how to retrieve its own data, because some
        # widgets split data over several HTML fields.
        return widget.value_from_datadict(self.data, self.files, html_name)

    @property
    def template_name(self):
        return self.renderer.form_template_name

    def get_context(self):
        """
        Returns a dictionary containing the context for rendering a form, including the form instance, 
        visible and hidden fields, and any form-level errors.
        """
        fields = []
        hidden_fields = []
        top_errors = self.non_field_errors().copy()
        for name, bf in self._bound_items():
            if bf.is_hidden:
                if bf.errors:
                    top_errors += [
                        _("(Hidden field %(name)s) %(error)s")
                        % {"name": name, "error": str(e)}
                        for e in bf.errors
                    ]
                hidden_fields.append(bf)
            else:
                fields.append((bf, bf.errors))
        return {
            "form": self,
            "fields": fields,
            "hidden_fields": hidden_fields,
            "errors": top_errors,
        }

    def non_field_errors(self):
        """
        Return an ErrorList of errors that aren't associated with a particular
        field -- i.e., from Form.clean(). Return an empty ErrorList if there
        are none.
        """
        return self.errors.get(
            NON_FIELD_ERRORS,
            self.error_class(error_class="nonfield", renderer=self.renderer),
        )

    def add_error(self, field, error):
        """
        Associates error information with a form field or marks form-level errors.

        The field name and corresponding error details are used to update the internal error tracking data structure. The function can handle various types of input for errors, including strings, ValidationError instances, and collections of these types. It also enforces consistency rules to prevent invalid error reporting configurations.
        """
        if not isinstance(error, ValidationError):
            # Normalize to ValidationError and let its constructor
            # do the hard work of making sense of the input.
            error = ValidationError(error)

        if hasattr(error, "error_dict"):
            if field is not None:
                raise TypeError(
                    "The argument `field` must be `None` when the `error` "
                    "argument contains errors for multiple fields."
                )
            else:
                error = error.error_dict
        else:
            error = {field or NON_FIELD_ERRORS: error.error_list}

        for field, error_list in error.items():
            if field not in self.errors:
                if field != NON_FIELD_ERRORS and field not in self.fields:
                    raise ValueError(
                        "'%s' has no field named '%s'."
                        % (self.__class__.__name__, field)
                    )
                if field == NON_FIELD_ERRORS:
                    self._errors[field] = self.error_class(
                        error_class="nonfield", renderer=self.renderer
                    )
                else:
                    self._errors[field] = self.error_class(renderer=self.renderer)
            self._errors[field].extend(error_list)
            if field in self.cleaned_data:
                del self.cleaned_data[field]

    def has_error(self, field, code=None):
        return field in self.errors and (
            code is None
            or any(error.code == code for error in self.errors.as_data()[field])
        )

    def full_clean(self):
        """

        Perform a thorough validation of the entire form data, populating error messages and cleaned data dictionaries.

        """
        self._errors = ErrorDict()
        if not self.is_bound:  # Stop further processing.
            return
        self.cleaned_data = {}
        # If the form is permitted to be empty, and none of the form data has
        # changed from the initial data, short circuit any validation.
        if self.empty_permitted and not self.has_changed():
            return

        self._clean_fields()
        self._clean_form()
        self._post_clean()

    def _clean_fields(self):
        """
        Cleans each field in the form, applying field-specific cleaning rules and validation, 
        and stores the cleaned data in the :attr:`cleaned_data` attribute. 
        Any validation errors that occur during cleaning are added to the form's errors.
        """
        for name, bf in self._bound_items():
            field = bf.field
            try:
                self.cleaned_data[name] = field._clean_bound_field(bf)
                if hasattr(self, "clean_%s" % name):
                    value = getattr(self, "clean_%s" % name)()
                    self.cleaned_data[name] = value
            except ValidationError as e:
                self.add_error(name, e)

    def _clean_form(self):
        """
        Cleans the form data, handling validation errors and storing the cleaned data if successful.\"\"\"

        \"\"\"
         :raises: ValidationError if validation fails
         :note: If validation is successful, the cleaned data is stored in :attr:`cleaned_data`

        """
        try:
            cleaned_data = self.clean()
        except ValidationError as e:
            self.add_error(None, e)
        else:
            if cleaned_data is not None:
                self.cleaned_data = cleaned_data

    def _post_clean(self):
        """
        An internal hook for performing additional cleaning after form cleaning
        is complete. Used for model validation in model forms.
        """
        pass

    def clean(self):
        """
        Hook for doing any extra form-wide cleaning after Field.clean() has been
        called on every field. Any ValidationError raised by this method will
        not be associated with a particular field; it will have a special-case
        association with the field named '__all__'.
        """
        return self.cleaned_data

    def has_changed(self):
        """Return True if data differs from initial."""
        return bool(self.changed_data)

    @cached_property
    def changed_data(self):
        return [name for name, bf in self._bound_items() if bf._has_changed()]

    @property
    def media(self):
        """
        Returns the aggregate media needed to render all widgets on this form, 
        combining the media requirements of each field's widget.
        """
        media = Media()
        for field in self.fields.values():
            media += field.widget.media
        return media

    def is_multipart(self):
        """
        Return True if the form needs to be multipart-encoded, i.e. it has
        FileInput, or False otherwise.
        """
        return any(field.widget.needs_multipart_form for field in self.fields.values())

    def hidden_fields(self):
        """
        Return a list of all the BoundField objects that are hidden fields.
        Useful for manual form layout in templates.
        """
        return [field for field in self if field.is_hidden]

    def visible_fields(self):
        """
        Return a list of BoundField objects that aren't hidden fields.
        The opposite of the hidden_fields() method.
        """
        return [field for field in self if not field.is_hidden]

    def get_initial_for_field(self, field, field_name):
        """
        Returns the initial data for a given form field, preferring form initial data over field initial data. Any callable values are evaluated and datetime values are truncated if the field does not support microseconds.
        """
        value = self.initial.get(field_name, field.initial)
        if callable(value):
            value = value()
        # If this is an auto-generated default date, nix the microseconds
        # for standardized handling. See #22502.
        if (
            isinstance(value, (datetime.datetime, datetime.time))
            and not field.widget.supports_microseconds
        ):
            value = value.replace(microsecond=0)
        return value


class Form(BaseForm, metaclass=DeclarativeFieldsMetaclass):
    "A collection of Fields, plus their associated data."
    # This is a separate class from BaseForm in order to abstract the way
    # self.fields is specified. This class (Form) is the one that does the
    # fancy metaclass stuff purely for the semantic sugar -- it allows one
    # to define a form using declarative syntax.
    # BaseForm itself has no way of designating self.fields.
