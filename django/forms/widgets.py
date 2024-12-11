"""
HTML Widget classes
"""

import copy
import datetime
import warnings
from collections import defaultdict
from graphlib import CycleError, TopologicalSorter
from itertools import chain

from django.forms.utils import to_current_timezone
from django.templatetags.static import static
from django.utils import formats
from django.utils.choices import normalize_choices
from django.utils.dates import MONTHS
from django.utils.formats import get_format
from django.utils.html import format_html, html_safe
from django.utils.regex_helper import _lazy_re_compile
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .renderers import get_default_renderer

__all__ = (
    "Media",
    "MediaDefiningClass",
    "Widget",
    "TextInput",
    "NumberInput",
    "EmailInput",
    "URLInput",
    "PasswordInput",
    "HiddenInput",
    "MultipleHiddenInput",
    "FileInput",
    "ClearableFileInput",
    "Textarea",
    "DateInput",
    "DateTimeInput",
    "TimeInput",
    "CheckboxInput",
    "Select",
    "NullBooleanSelect",
    "SelectMultiple",
    "RadioSelect",
    "CheckboxSelectMultiple",
    "MultiWidget",
    "SplitDateTimeWidget",
    "SplitHiddenDateTimeWidget",
    "SelectDateWidget",
)

MEDIA_TYPES = ("css", "js")


class MediaOrderConflictWarning(RuntimeWarning):
    pass


@html_safe
class Media:
    def __init__(self, media=None, css=None, js=None):
        """
        Initializes the object with media, CSS, and JavaScript resources.

        The function accepts optional parameters for media, CSS, and JavaScript resources. 
        If media is provided, it retrieves the CSS and JavaScript resources from it. 
        Otherwise, it uses the provided CSS and JavaScript resources, defaulting to an empty dictionary for CSS and an empty list for JavaScript if they are not specified. 
        The resources are then stored in internal lists for later use.
        """
        if media is not None:
            css = getattr(media, "css", {})
            js = getattr(media, "js", [])
        else:
            if css is None:
                css = {}
            if js is None:
                js = []
        self._css_lists = [css]
        self._js_lists = [js]

    def __repr__(self):
        return "Media(css=%r, js=%r)" % (self._css, self._js)

    def __str__(self):
        return self.render()

    @property
    def _css(self):
        """
        Returns a compiled CSS dictionary with media queries merged.

        This property aggregates CSS rules from multiple lists, grouping them by media query.
        Each media query's rules are then merged into a single list, allowing for easy access to the
        compiled CSS data. The resulting dictionary is keyed by media query, with values being
        the merged lists of CSS rules for each query.
        """
        css = defaultdict(list)
        for css_list in self._css_lists:
            for medium, sublist in css_list.items():
                css[medium].append(sublist)
        return {medium: self.merge(*lists) for medium, lists in css.items()}

    @property
    def _js(self):
        return self.merge(*self._js_lists)

    def render(self):
        return mark_safe(
            "\n".join(
                chain.from_iterable(
                    getattr(self, "render_" + name)() for name in MEDIA_TYPES
                )
            )
        )

    def render_js(self):
        return [
            (
                path.__html__()
                if hasattr(path, "__html__")
                else format_html('<script src="{}"></script>', self.absolute_path(path))
            )
            for path in self._js
        ]

    def render_css(self):
        # To keep rendering order consistent, we can't just iterate over items().
        # We need to sort the keys, and iterate over the sorted list.
        """
        Renders CSS links for the current object, sorting media types and generating HTML tags.

        The function generates a sequence of HTML link tags, one for each CSS path, with the 'media' attribute set to the corresponding media type.
        It iterates over the sorted media types and, for each type, iterates over the associated CSS paths.
        For each path, it generates an HTML link tag with the 'href' attribute set to the absolute path of the CSS file and the 'rel' attribute set to 'stylesheet'.
        If a path object has an '__html__' method, it is used to generate the HTML tag; otherwise, a default format is used.
        The resulting sequence of HTML tags is returned, allowing for easy inclusion in a larger HTML document.
        """
        media = sorted(self._css)
        return chain.from_iterable(
            [
                (
                    path.__html__()
                    if hasattr(path, "__html__")
                    else format_html(
                        '<link href="{}" media="{}" rel="stylesheet">',
                        self.absolute_path(path),
                        medium,
                    )
                )
                for path in self._css[medium]
            ]
            for medium in media
        )

    def absolute_path(self, path):
        """
        Given a relative or absolute path to a static asset, return an absolute
        path. An absolute path will be returned unchanged while a relative path
        will be passed to django.templatetags.static.static().
        """
        if path.startswith(("http://", "https://", "/")):
            return path
        return static(path)

    def __getitem__(self, name):
        """Return a Media object that only contains media of the given type."""
        if name in MEDIA_TYPES:
            return Media(**{str(name): getattr(self, "_" + name)})
        raise KeyError('Unknown media type "%s"' % name)

    @staticmethod
    def merge(*lists):
        """
        Merge lists while trying to keep the relative order of the elements.
        Warn if the lists have the same elements in a different relative order.

        For static assets it can be important to have them included in the DOM
        in a certain order. In JavaScript you may not be able to reference a
        global or in CSS you might want to override a style.
        """
        ts = TopologicalSorter()
        for head, *tail in filter(None, lists):
            ts.add(head)  # Ensure that the first items are included.
            for item in tail:
                if head != item:  # Avoid circular dependency to self.
                    ts.add(item, head)
                head = item
        try:
            return list(ts.static_order())
        except CycleError:
            warnings.warn(
                "Detected duplicate Media files in an opposite order: {}".format(
                    ", ".join(repr(list_) for list_ in lists)
                ),
                MediaOrderConflictWarning,
            )
            return list(dict.fromkeys(chain.from_iterable(filter(None, lists))))

    def __add__(self, other):
        """
        Combine two Media objects by merging their CSS and JavaScript lists.

        This operation returns a new Media object that contains all unique CSS and JavaScript items from both the current object and the object being added. Duplicate items are automatically removed from the resulting object, ensuring a concise and efficient representation of the combined media resources.
        """
        combined = Media()
        combined._css_lists = self._css_lists[:]
        combined._js_lists = self._js_lists[:]
        for item in other._css_lists:
            if item and item not in self._css_lists:
                combined._css_lists.append(item)
        for item in other._js_lists:
            if item and item not in self._js_lists:
                combined._js_lists.append(item)
        return combined


def media_property(cls):
    """
    Property decorator to manage media properties for a class.

    This property provides a convenient way to define and extend media definitions
    for a class. It allows subclasses to add or override media definitions while
    still inheriting the media definitions from their parent classes.

    The property returns a Media object that represents the combined media definitions
    of the class and its parent classes. If the class defines a Media class attribute,
    it will be used to extend or override the parent class's media definitions.

    The extend behavior can be controlled by setting the `extend` attribute on the
    Media class attribute. If `extend` is True, the class's media definitions will
    be added to the parent class's media definitions. If `extend` is a list of medium
    names, only those mediums will be inherited from the parent class.

    This property is designed to be used as a decorator for a class, allowing the
    class to easily manage its media properties and inherit media definitions from
    its parent classes.
    """
    def _media(self):
        # Get the media property of the superclass, if it exists
        """
        Returns the media definition for the current class, extending the media 
        from its superclass if applicable.

        The method checks if the current class has a Media definition. If it does, 
        it returns the Media definition, possibly extended with the superclass's 
        media, depending on the `extend` attribute of the Media definition.

        If the `extend` attribute is True, the superclass's media is fully included.
        If `extend` is a list of medium types, only those medium types from the 
        superclass's media are included. If `extend` is not provided or is False, 
        only the current class's media definition is returned.

        If the current class does not have a Media definition, the method returns 
        the media from its superclass, or an empty Media object if the superclass 
        does not have a media definition either.
        """
        sup_cls = super(cls, self)
        try:
            base = sup_cls.media
        except AttributeError:
            base = Media()

        # Get the media definition for this class
        definition = getattr(cls, "Media", None)
        if definition:
            extend = getattr(definition, "extend", True)
            if extend:
                if extend is True:
                    m = base
                else:
                    m = Media()
                    for medium in extend:
                        m += base[medium]
                return m + Media(definition)
            return Media(definition)
        return base

    return property(_media)


class MediaDefiningClass(type):
    """
    Metaclass for classes that can have media definitions.
    """

    def __new__(mcs, name, bases, attrs):
        """

        Metaclass constructor to create a new class instance.

        Automatically adds a 'media' property to the class if it does not already exist.
        The 'media' property is generated using the media_property function, which is
        applied to the newly created class.

        This allows subclasses to use the 'media' property without having to define it
        explicitly, simplifying the process of creating classes that require media handling.

        """
        new_class = super().__new__(mcs, name, bases, attrs)

        if "media" not in attrs:
            new_class.media = media_property(new_class)

        return new_class


class Widget(metaclass=MediaDefiningClass):
    needs_multipart_form = False  # Determines does this widget need multipart form
    is_localized = False
    is_required = False
    supports_microseconds = True
    use_fieldset = False

    def __init__(self, attrs=None):
        self.attrs = {} if attrs is None else attrs.copy()

    def __deepcopy__(self, memo):
        """
        Override of the __deepcopy__ method to create a deep copy of the current object.

        This method ensures that a new, independent copy of the object is created, including its attributes. The memo dictionary is used to keep track of objects that have already been copied, to avoid infinite recursion and improve performance.

        The resulting copy has the same attributes and values as the original object, but is a separate entity that can be modified without affecting the original.

        :param memo: A dictionary that maps the ids of objects to their copies, used to optimize the copying process.
        :return: A deep copy of the current object.

        """
        obj = copy.copy(self)
        obj.attrs = self.attrs.copy()
        memo[id(self)] = obj
        return obj

    @property
    def is_hidden(self):
        return self.input_type == "hidden" if hasattr(self, "input_type") else False

    def subwidgets(self, name, value, attrs=None):
        """
        Renders a subwidget for the given name and value.

        :name: The name of the subwidget to be rendered.
        :value: The value associated with the subwidget.
        :attrs: Optional attributes to customize the subwidget. Defaults to None.

        Yields the rendered subwidget context, providing access to the widget object.
        This allows for further customization or extension of the subwidget's behavior.

        Note: This method relies on the `get_context` method to prepare the subwidget context.

        """
        context = self.get_context(name, value, attrs)
        yield context["widget"]

    def format_value(self, value):
        """
        Return a value as it should appear when rendered in a template.
        """
        if value == "" or value is None:
            return None
        if self.is_localized:
            return formats.localize_input(value)
        return str(value)

    def get_context(self, name, value, attrs):
        return {
            "widget": {
                "name": name,
                "is_hidden": self.is_hidden,
                "required": self.is_required,
                "value": self.format_value(value),
                "attrs": self.build_attrs(self.attrs, attrs),
                "template_name": self.template_name,
            },
        }

    def render(self, name, value, attrs=None, renderer=None):
        """Render the widget as an HTML string."""
        context = self.get_context(name, value, attrs)
        return self._render(self.template_name, context, renderer)

    def _render(self, template_name, context, renderer=None):
        """

        Renders a template with the provided context.

        :param template_name: The name of the template to render.
        :param context: The context data to be used during rendering.
        :param renderer: The renderer to use for rendering the template. If not provided, the default renderer is used.

        :returns: The rendered template content, marked as safe HTML.

        """
        if renderer is None:
            renderer = get_default_renderer()
        return mark_safe(renderer.render(template_name, context))

    def build_attrs(self, base_attrs, extra_attrs=None):
        """Build an attribute dictionary."""
        return {**base_attrs, **(extra_attrs or {})}

    def value_from_datadict(self, data, files, name):
        """
        Given a dictionary of data and this widget's name, return the value
        of this widget or None if it's not provided.
        """
        return data.get(name)

    def value_omitted_from_data(self, data, files, name):
        return name not in data

    def id_for_label(self, id_):
        """
        Return the HTML ID attribute of this Widget for use by a <label>, given
        the ID of the field. Return an empty string if no ID is available.

        This hook is necessary because some widgets have multiple HTML
        elements and, thus, multiple IDs. In that case, this method should
        return an ID value that corresponds to the first ID in the widget's
        tags.
        """
        return id_

    def use_required_attribute(self, initial):
        return not self.is_hidden


class Input(Widget):
    """
    Base class for all <input> widgets.
    """

    input_type = None  # Subclasses must define this.
    template_name = "django/forms/widgets/input.html"

    def __init__(self, attrs=None):
        if attrs is not None:
            attrs = attrs.copy()
            self.input_type = attrs.pop("type", self.input_type)
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["type"] = self.input_type
        return context


class TextInput(Input):
    input_type = "text"
    template_name = "django/forms/widgets/text.html"


class NumberInput(Input):
    input_type = "number"
    template_name = "django/forms/widgets/number.html"


class EmailInput(Input):
    input_type = "email"
    template_name = "django/forms/widgets/email.html"


class URLInput(Input):
    input_type = "url"
    template_name = "django/forms/widgets/url.html"


class PasswordInput(Input):
    input_type = "password"
    template_name = "django/forms/widgets/password.html"

    def __init__(self, attrs=None, render_value=False):
        super().__init__(attrs)
        self.render_value = render_value

    def get_context(self, name, value, attrs):
        if not self.render_value:
            value = None
        return super().get_context(name, value, attrs)


class HiddenInput(Input):
    input_type = "hidden"
    template_name = "django/forms/widgets/hidden.html"


class MultipleHiddenInput(HiddenInput):
    """
    Handle <input type="hidden"> for fields that have a list
    of values.
    """

    template_name = "django/forms/widgets/multiple_hidden.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        final_attrs = context["widget"]["attrs"]
        id_ = context["widget"]["attrs"].get("id")

        subwidgets = []
        for index, value_ in enumerate(context["widget"]["value"]):
            widget_attrs = final_attrs.copy()
            if id_:
                # An ID attribute was given. Add a numeric index as a suffix
                # so that the inputs don't all have the same ID attribute.
                widget_attrs["id"] = "%s_%s" % (id_, index)
            widget = HiddenInput()
            widget.is_required = self.is_required
            subwidgets.append(widget.get_context(name, value_, widget_attrs)["widget"])

        context["widget"]["subwidgets"] = subwidgets
        return context

    def value_from_datadict(self, data, files, name):
        try:
            getter = data.getlist
        except AttributeError:
            getter = data.get
        return getter(name)

    def format_value(self, value):
        return [] if value is None else value


class FileInput(Input):
    allow_multiple_selected = False
    input_type = "file"
    needs_multipart_form = True
    template_name = "django/forms/widgets/file.html"

    def __init__(self, attrs=None):
        if (
            attrs is not None
            and not self.allow_multiple_selected
            and attrs.get("multiple", False)
        ):
            raise ValueError(
                "%s doesn't support uploading multiple files."
                % self.__class__.__qualname__
            )
        if self.allow_multiple_selected:
            if attrs is None:
                attrs = {"multiple": True}
            else:
                attrs.setdefault("multiple", True)
        super().__init__(attrs)

    def format_value(self, value):
        """File input never renders a value."""
        return

    def value_from_datadict(self, data, files, name):
        "File widgets take data from FILES, not POST"
        getter = files.get
        if self.allow_multiple_selected:
            try:
                getter = files.getlist
            except AttributeError:
                pass
        return getter(name)

    def value_omitted_from_data(self, data, files, name):
        return name not in files

    def use_required_attribute(self, initial):
        return super().use_required_attribute(initial) and not initial


FILE_INPUT_CONTRADICTION = object()


class ClearableFileInput(FileInput):
    clear_checkbox_label = _("Clear")
    initial_text = _("Currently")
    input_text = _("Change")
    template_name = "django/forms/widgets/clearable_file_input.html"
    checked = False

    def clear_checkbox_name(self, name):
        """
        Given the name of the file input, return the name of the clear checkbox
        input.
        """
        return name + "-clear"

    def clear_checkbox_id(self, name):
        """
        Given the name of the clear checkbox input, return the HTML id for it.
        """
        return name + "_id"

    def is_initial(self, value):
        """
        Return whether value is considered to be initial value.
        """
        return bool(value and getattr(value, "url", False))

    def format_value(self, value):
        """
        Return the file object if it has a defined url attribute.
        """
        if self.is_initial(value):
            return value

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        checkbox_name = self.clear_checkbox_name(name)
        checkbox_id = self.clear_checkbox_id(checkbox_name)
        context["widget"].update(
            {
                "checkbox_name": checkbox_name,
                "checkbox_id": checkbox_id,
                "is_initial": self.is_initial(value),
                "input_text": self.input_text,
                "initial_text": self.initial_text,
                "clear_checkbox_label": self.clear_checkbox_label,
            }
        )
        context["widget"]["attrs"].setdefault("disabled", False)
        context["widget"]["attrs"]["checked"] = self.checked
        return context

    def value_from_datadict(self, data, files, name):
        upload = super().value_from_datadict(data, files, name)
        self.checked = self.clear_checkbox_name(name) in data
        if not self.is_required and CheckboxInput().value_from_datadict(
            data, files, self.clear_checkbox_name(name)
        ):
            if upload:
                # If the user contradicts themselves (uploads a new file AND
                # checks the "clear" checkbox), we return a unique marker
                # object that FileField will turn into a ValidationError.
                return FILE_INPUT_CONTRADICTION
            # False signals to clear any existing value, as opposed to just None
            return False
        return upload

    def value_omitted_from_data(self, data, files, name):
        return (
            super().value_omitted_from_data(data, files, name)
            and self.clear_checkbox_name(name) not in data
        )


class Textarea(Widget):
    template_name = "django/forms/widgets/textarea.html"

    def __init__(self, attrs=None):
        # Use slightly better defaults than HTML's 20x2 box
        default_attrs = {"cols": "40", "rows": "10"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class DateTimeBaseInput(TextInput):
    format_key = ""
    supports_microseconds = False

    def __init__(self, attrs=None, format=None):
        super().__init__(attrs)
        self.format = format or None

    def format_value(self, value):
        return formats.localize_input(
            value, self.format or formats.get_format(self.format_key)[0]
        )


class DateInput(DateTimeBaseInput):
    format_key = "DATE_INPUT_FORMATS"
    template_name = "django/forms/widgets/date.html"


class DateTimeInput(DateTimeBaseInput):
    format_key = "DATETIME_INPUT_FORMATS"
    template_name = "django/forms/widgets/datetime.html"


class TimeInput(DateTimeBaseInput):
    format_key = "TIME_INPUT_FORMATS"
    template_name = "django/forms/widgets/time.html"


# Defined at module level so that CheckboxInput is picklable (#17976)
def boolean_check(v):
    return not (v is False or v is None or v == "")


class CheckboxInput(Input):
    input_type = "checkbox"
    template_name = "django/forms/widgets/checkbox.html"

    def __init__(self, attrs=None, check_test=None):
        """
        Initialize a class instance with optional attributes and test checking configuration.

        :param attrs: Optional attributes to initialize the instance with
        :param check_test: Optional test checking function, defaults to boolean_check if not provided
        :type attrs: dict or None
        :type check_test: callable or None
        :returns: None
        :note: The check_test function is used to validate test conditions, the default boolean_check function is used if not specified.
        """
        super().__init__(attrs)
        # check_test is a callable that takes a value and returns True
        # if the checkbox should be checked for that value.
        self.check_test = boolean_check if check_test is None else check_test

    def format_value(self, value):
        """Only return the 'value' attribute if value isn't empty."""
        if value is True or value is False or value is None or value == "":
            return
        return str(value)

    def get_context(self, name, value, attrs):
        if self.check_test(value):
            attrs = {**(attrs or {}), "checked": True}
        return super().get_context(name, value, attrs)

    def value_from_datadict(self, data, files, name):
        if name not in data:
            # A missing value means False because HTML form submission does not
            # send results for unselected checkboxes.
            return False
        value = data.get(name)
        # Translate true and false strings to boolean values.
        values = {"true": True, "false": False}
        if isinstance(value, str):
            value = values.get(value.lower(), value)
        return bool(value)

    def value_omitted_from_data(self, data, files, name):
        # HTML checkboxes don't appear in POST data if not checked, so it's
        # never known if the value is actually omitted.
        return False


class ChoiceWidget(Widget):
    allow_multiple_selected = False
    input_type = None
    template_name = None
    option_template_name = None
    add_id_index = True
    checked_attribute = {"checked": True}
    option_inherits_attrs = True

    def __init__(self, attrs=None, choices=()):
        super().__init__(attrs)
        self.choices = choices

    def __deepcopy__(self, memo):
        obj = copy.copy(self)
        obj.attrs = self.attrs.copy()
        obj.choices = copy.copy(self.choices)
        memo[id(self)] = obj
        return obj

    def subwidgets(self, name, value, attrs=None):
        """
        Yield all "subwidgets" of this widget. Used to enable iterating
        options from a BoundField for choice widgets.
        """
        value = self.format_value(value)
        yield from self.options(name, value, attrs)

    def options(self, name, value, attrs=None):
        """Yield a flat list of options for this widget."""
        for group in self.optgroups(name, value, attrs):
            yield from group[1]

    def optgroups(self, name, value, attrs=None):
        """Return a list of optgroups for this widget."""
        groups = []
        has_selected = False

        for index, (option_value, option_label) in enumerate(self.choices):
            if option_value is None:
                option_value = ""

            subgroup = []
            if isinstance(option_label, (list, tuple)):
                group_name = option_value
                subindex = 0
                choices = option_label
            else:
                group_name = None
                subindex = None
                choices = [(option_value, option_label)]
            groups.append((group_name, subgroup, index))

            for subvalue, sublabel in choices:
                selected = (not has_selected or self.allow_multiple_selected) and str(
                    subvalue
                ) in value
                has_selected |= selected
                subgroup.append(
                    self.create_option(
                        name,
                        subvalue,
                        sublabel,
                        selected,
                        index,
                        subindex=subindex,
                        attrs=attrs,
                    )
                )
                if subindex is not None:
                    subindex += 1
        return groups

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        index = str(index) if subindex is None else "%s_%s" % (index, subindex)
        option_attrs = (
            self.build_attrs(self.attrs, attrs) if self.option_inherits_attrs else {}
        )
        if selected:
            option_attrs.update(self.checked_attribute)
        if "id" in option_attrs:
            option_attrs["id"] = self.id_for_label(option_attrs["id"], index)
        return {
            "name": name,
            "value": value,
            "label": label,
            "selected": selected,
            "index": index,
            "attrs": option_attrs,
            "type": self.input_type,
            "template_name": self.option_template_name,
            "wrap_label": True,
        }

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["optgroups"] = self.optgroups(
            name, context["widget"]["value"], attrs
        )
        return context

    def id_for_label(self, id_, index="0"):
        """
        Use an incremented id for each option where the main widget
        references the zero index.
        """
        if id_ and self.add_id_index:
            id_ = "%s_%s" % (id_, index)
        return id_

    def value_from_datadict(self, data, files, name):
        getter = data.get
        if self.allow_multiple_selected:
            try:
                getter = data.getlist
            except AttributeError:
                pass
        return getter(name)

    def format_value(self, value):
        """Return selected values as a list."""
        if value is None and self.allow_multiple_selected:
            return []
        if not isinstance(value, (tuple, list)):
            value = [value]
        return [str(v) if v is not None else "" for v in value]

    @property
    def choices(self):
        return self._choices

    @choices.setter
    def choices(self, value):
        self._choices = normalize_choices(value)


class Select(ChoiceWidget):
    input_type = "select"
    template_name = "django/forms/widgets/select.html"
    option_template_name = "django/forms/widgets/select_option.html"
    add_id_index = False
    checked_attribute = {"selected": True}
    option_inherits_attrs = False

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if self.allow_multiple_selected:
            context["widget"]["attrs"]["multiple"] = True
        return context

    @staticmethod
    def _choice_has_empty_value(choice):
        """Return True if the choice's value is empty string or None."""
        value, _ = choice
        return value is None or value == ""

    def use_required_attribute(self, initial):
        """
        Don't render 'required' if the first <option> has a value, as that's
        invalid HTML.
        """
        use_required_attribute = super().use_required_attribute(initial)
        # 'required' is always okay for <select multiple>.
        if self.allow_multiple_selected:
            return use_required_attribute

        first_choice = next(iter(self.choices), None)
        return (
            use_required_attribute
            and first_choice is not None
            and self._choice_has_empty_value(first_choice)
        )


class NullBooleanSelect(Select):
    """
    A Select Widget intended to be used with NullBooleanField.
    """

    def __init__(self, attrs=None):
        choices = (
            ("unknown", _("Unknown")),
            ("true", _("Yes")),
            ("false", _("No")),
        )
        super().__init__(attrs, choices)

    def format_value(self, value):
        try:
            return {
                True: "true",
                False: "false",
                "true": "true",
                "false": "false",
                # For backwards compatibility with Django < 2.2.
                "2": "true",
                "3": "false",
            }[value]
        except KeyError:
            return "unknown"

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        return {
            True: True,
            "True": True,
            "False": False,
            False: False,
            "true": True,
            "false": False,
            # For backwards compatibility with Django < 2.2.
            "2": True,
            "3": False,
        }.get(value)


class SelectMultiple(Select):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        """
        Retrieves a value from a dictionary-like object, falling back to a single value retrieval if the object does not support multiple values.

        :param data: Dictionary-like object containing the data to retrieve from.
        :param files: Not used in this implementation.
        :param name: Name of the value to retrieve from the data object.
        :return: The retrieved value or values associated with the given name.

        Note: This function adapts its retrieval method based on the capabilities of the provided data object, allowing it to work with both single and multi-value data structures.
        """
        try:
            getter = data.getlist
        except AttributeError:
            getter = data.get
        return getter(name)

    def value_omitted_from_data(self, data, files, name):
        # An unselected <select multiple> doesn't appear in POST data, so it's
        # never known if the value is actually omitted.
        return False


class RadioSelect(ChoiceWidget):
    input_type = "radio"
    template_name = "django/forms/widgets/radio.html"
    option_template_name = "django/forms/widgets/radio_option.html"
    use_fieldset = True

    def id_for_label(self, id_, index=None):
        """
        Don't include for="field_0" in <label> to improve accessibility when
        using a screen reader, in addition clicking such a label would toggle
        the first input.
        """
        if index is None:
            return ""
        return super().id_for_label(id_, index)


class CheckboxSelectMultiple(RadioSelect):
    allow_multiple_selected = True
    input_type = "checkbox"
    template_name = "django/forms/widgets/checkbox_select.html"
    option_template_name = "django/forms/widgets/checkbox_option.html"

    def use_required_attribute(self, initial):
        # Don't use the 'required' attribute because browser validation would
        # require all checkboxes to be checked instead of at least one.
        return False

    def value_omitted_from_data(self, data, files, name):
        # HTML checkboxes don't appear in POST data if not checked, so it's
        # never known if the value is actually omitted.
        return False


class MultiWidget(Widget):
    """
    A widget that is composed of multiple widgets.

    In addition to the values added by Widget.get_context(), this widget
    adds a list of subwidgets to the context as widget['subwidgets'].
    These can be looped over and rendered like normal widgets.

    You'll probably want to use this class with MultiValueField.
    """

    template_name = "django/forms/widgets/multiwidget.html"
    use_fieldset = True

    def __init__(self, widgets, attrs=None):
        if isinstance(widgets, dict):
            self.widgets_names = [("_%s" % name) if name else "" for name in widgets]
            widgets = widgets.values()
        else:
            self.widgets_names = ["_%s" % i for i in range(len(widgets))]
        self.widgets = [w() if isinstance(w, type) else w for w in widgets]
        super().__init__(attrs)

    @property
    def is_hidden(self):
        return all(w.is_hidden for w in self.widgets)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if self.is_localized:
            for widget in self.widgets:
                widget.is_localized = self.is_localized
        # value is a list/tuple of values, each corresponding to a widget
        # in self.widgets.
        if not isinstance(value, (list, tuple)):
            value = self.decompress(value)

        final_attrs = context["widget"]["attrs"]
        input_type = final_attrs.pop("type", None)
        id_ = final_attrs.get("id")
        subwidgets = []
        for i, (widget_name, widget) in enumerate(
            zip(self.widgets_names, self.widgets)
        ):
            if input_type is not None:
                widget.input_type = input_type
            widget_name = name + widget_name
            try:
                widget_value = value[i]
            except IndexError:
                widget_value = None
            if id_:
                widget_attrs = final_attrs.copy()
                widget_attrs["id"] = "%s_%s" % (id_, i)
            else:
                widget_attrs = final_attrs
            subwidgets.append(
                widget.get_context(widget_name, widget_value, widget_attrs)["widget"]
            )
        context["widget"]["subwidgets"] = subwidgets
        return context

    def id_for_label(self, id_):
        return ""

    def value_from_datadict(self, data, files, name):
        return [
            widget.value_from_datadict(data, files, name + widget_name)
            for widget_name, widget in zip(self.widgets_names, self.widgets)
        ]

    def value_omitted_from_data(self, data, files, name):
        return all(
            widget.value_omitted_from_data(data, files, name + widget_name)
            for widget_name, widget in zip(self.widgets_names, self.widgets)
        )

    def decompress(self, value):
        """
        Return a list of decompressed values for the given compressed value.
        The given value can be assumed to be valid, but not necessarily
        non-empty.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def _get_media(self):
        """
        Media for a multiwidget is the combination of all media of the
        subwidgets.
        """
        media = Media()
        for w in self.widgets:
            media += w.media
        return media

    media = property(_get_media)

    def __deepcopy__(self, memo):
        obj = super().__deepcopy__(memo)
        obj.widgets = copy.deepcopy(self.widgets)
        return obj

    @property
    def needs_multipart_form(self):
        return any(w.needs_multipart_form for w in self.widgets)


class SplitDateTimeWidget(MultiWidget):
    """
    A widget that splits datetime input into two <input type="text"> boxes.
    """

    supports_microseconds = False
    template_name = "django/forms/widgets/splitdatetime.html"

    def __init__(
        self,
        attrs=None,
        date_format=None,
        time_format=None,
        date_attrs=None,
        time_attrs=None,
    ):
        """
        Initializes a date and time input widget composite.

        This initializer allows for customization of the date and time input fields through various optional parameters.
        The attrs parameter sets common attributes for both date and time inputs, while date_attrs and time_attrs allow for specific overrides.
        The date_format and time_format parameters control the display and parsing format of the date and time inputs, respectively. 

        The widget composite is constructed by combining a DateInput and a TimeInput, using the specified formats and attributes.
        """
        widgets = (
            DateInput(
                attrs=attrs if date_attrs is None else date_attrs,
                format=date_format,
            ),
            TimeInput(
                attrs=attrs if time_attrs is None else time_attrs,
                format=time_format,
            ),
        )
        super().__init__(widgets)

    def decompress(self, value):
        if value:
            value = to_current_timezone(value)
            return [value.date(), value.time()]
        return [None, None]


class SplitHiddenDateTimeWidget(SplitDateTimeWidget):
    """
    A widget that splits datetime input into two <input type="hidden"> inputs.
    """

    template_name = "django/forms/widgets/splithiddendatetime.html"

    def __init__(
        self,
        attrs=None,
        date_format=None,
        time_format=None,
        date_attrs=None,
        time_attrs=None,
    ):
        """
        Initialize a custom form widget.

        This widget extends the base form widget by setting the input type of all its child widgets to 'hidden'.

        It accepts several optional parameters to customize its behavior:

        * attrs: additional HTML attributes for the widget
        * date_format and time_format: formats for date and time fields
        * date_attrs and time_attrs: additional attributes for date and time fields

        These parameters allow for flexible customization of the widget's appearance and functionality. Upon initialization, all child widgets are configured to be hidden input fields.
        """
        super().__init__(attrs, date_format, time_format, date_attrs, time_attrs)
        for widget in self.widgets:
            widget.input_type = "hidden"


class SelectDateWidget(Widget):
    """
    A widget that splits date input into three <select> boxes.

    This also serves as an example of a Widget that has more than one HTML
    element and hence implements value_from_datadict.
    """

    none_value = ("", "---")
    month_field = "%s_month"
    day_field = "%s_day"
    year_field = "%s_year"
    template_name = "django/forms/widgets/select_date.html"
    input_type = "select"
    select_widget = Select
    date_re = _lazy_re_compile(r"(\d{4}|0)-(\d\d?)-(\d\d?)$")
    use_fieldset = True

    def __init__(self, attrs=None, years=None, months=None, empty_label=None):
        self.attrs = attrs or {}

        # Optional list or tuple of years to use in the "year" select box.
        if years:
            self.years = years
        else:
            this_year = datetime.date.today().year
            self.years = range(this_year, this_year + 10)

        # Optional dict of months to use in the "month" select box.
        if months:
            self.months = months
        else:
            self.months = MONTHS

        # Optional string, list, or tuple to use as empty_label.
        if isinstance(empty_label, (list, tuple)):
            if not len(empty_label) == 3:
                raise ValueError("empty_label list/tuple must have 3 elements.")

            self.year_none_value = ("", empty_label[0])
            self.month_none_value = ("", empty_label[1])
            self.day_none_value = ("", empty_label[2])
        else:
            if empty_label is not None:
                self.none_value = ("", empty_label)

            self.year_none_value = self.none_value
            self.month_none_value = self.none_value
            self.day_none_value = self.none_value

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        date_context = {}
        year_choices = [(i, str(i)) for i in self.years]
        if not self.is_required:
            year_choices.insert(0, self.year_none_value)
        year_name = self.year_field % name
        date_context["year"] = self.select_widget(
            attrs, choices=year_choices
        ).get_context(
            name=year_name,
            value=context["widget"]["value"]["year"],
            attrs={**context["widget"]["attrs"], "id": "id_%s" % year_name},
        )
        month_choices = list(self.months.items())
        if not self.is_required:
            month_choices.insert(0, self.month_none_value)
        month_name = self.month_field % name
        date_context["month"] = self.select_widget(
            attrs, choices=month_choices
        ).get_context(
            name=month_name,
            value=context["widget"]["value"]["month"],
            attrs={**context["widget"]["attrs"], "id": "id_%s" % month_name},
        )
        day_choices = [(i, i) for i in range(1, 32)]
        if not self.is_required:
            day_choices.insert(0, self.day_none_value)
        day_name = self.day_field % name
        date_context["day"] = self.select_widget(
            attrs,
            choices=day_choices,
        ).get_context(
            name=day_name,
            value=context["widget"]["value"]["day"],
            attrs={**context["widget"]["attrs"], "id": "id_%s" % day_name},
        )
        subwidgets = []
        for field in self._parse_date_fmt():
            subwidgets.append(date_context[field]["widget"])
        context["widget"]["subwidgets"] = subwidgets
        return context

    def format_value(self, value):
        """
        Return a dict containing the year, month, and day of the current value.
        Use dict instead of a datetime to allow invalid dates such as February
        31 to display correctly.
        """
        year, month, day = None, None, None
        if isinstance(value, (datetime.date, datetime.datetime)):
            year, month, day = value.year, value.month, value.day
        elif isinstance(value, str):
            match = self.date_re.match(value)
            if match:
                # Convert any zeros in the date to empty strings to match the
                # empty option value.
                year, month, day = [int(val) or "" for val in match.groups()]
            else:
                input_format = get_format("DATE_INPUT_FORMATS")[0]
                try:
                    d = datetime.datetime.strptime(value, input_format)
                except ValueError:
                    pass
                else:
                    year, month, day = d.year, d.month, d.day
        return {"year": year, "month": month, "day": day}

    @staticmethod
    def _parse_date_fmt():
        fmt = get_format("DATE_FORMAT")
        escaped = False
        for char in fmt:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char in "Yy":
                yield "year"
            elif char in "bEFMmNn":
                yield "month"
            elif char in "dj":
                yield "day"

    def id_for_label(self, id_):
        """

        Generate an identifier based on a given label.

        This method takes an identifier :param:`id_` and attempts to append a date-based string.
        It iterates over the parsed date format and returns the concatenated string if successful.
        If no date format is found, it appends '_month' to the identifier.

        :param id_: The base identifier to be used in the concatenated string
        :return: The generated identifier string

        """
        for first_select in self._parse_date_fmt():
            return "%s_%s" % (id_, first_select)
        return "%s_month" % id_

    def value_from_datadict(self, data, files, name):
        y = data.get(self.year_field % name)
        m = data.get(self.month_field % name)
        d = data.get(self.day_field % name)
        if y == m == d == "":
            return None
        if y is not None and m is not None and d is not None:
            input_format = get_format("DATE_INPUT_FORMATS")[0]
            input_format = formats.sanitize_strftime_format(input_format)
            try:
                date_value = datetime.date(int(y), int(m), int(d))
            except ValueError:
                # Return pseudo-ISO dates with zeros for any unselected values,
                # e.g. '2017-0-23'.
                return "%s-%s-%s" % (y or 0, m or 0, d or 0)
            except OverflowError:
                return "0-0-0"
            return date_value.strftime(input_format)
        return data.get(name)

    def value_omitted_from_data(self, data, files, name):
        return not any(
            ("{}_{}".format(name, interval) in data)
            for interval in ("year", "month", "day")
        )
