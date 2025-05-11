"""
Form Widget classes specific to the Django admin site.
"""

import copy
import json

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import CASCADE, UUIDField
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.html import smart_urlquote
from django.utils.http import urlencode
from django.utils.text import Truncator
from django.utils.translation import get_language
from django.utils.translation import gettext as _


class FilteredSelectMultiple(forms.SelectMultiple):
    """
    A SelectMultiple with a JavaScript filter interface.

    Note that the resulting JavaScript assumes that the jsi18n
    catalog has been loaded in the page
    """

    class Media:
        js = [
            "admin/js/core.js",
            "admin/js/SelectBox.js",
            "admin/js/SelectFilter2.js",
        ]

    def __init__(self, verbose_name, is_stacked, attrs=None, choices=()):
        self.verbose_name = verbose_name
        self.is_stacked = is_stacked
        super().__init__(attrs, choices)

    def get_context(self, name, value, attrs):
        """

        Modifies the context for rendering a select filter widget, adding custom CSS classes 
        and data attributes for styling and JavaScript interaction.

        :param name: The name of the field.
        :param value: The value of the field.
        :param attrs: Additional attributes for the widget.
        :return: The modified context dictionary.

        """
        context = super().get_context(name, value, attrs)
        context["widget"]["attrs"]["class"] = "selectfilter"
        if self.is_stacked:
            context["widget"]["attrs"]["class"] += "stacked"
        context["widget"]["attrs"]["data-field-name"] = self.verbose_name
        context["widget"]["attrs"]["data-is-stacked"] = int(self.is_stacked)
        return context


class BaseAdminDateWidget(forms.DateInput):
    class Media:
        js = [
            "admin/js/calendar.js",
            "admin/js/admin/DateTimeShortcuts.js",
        ]

    def __init__(self, attrs=None, format=None):
        attrs = {"class": "vDateField", "size": "10", **(attrs or {})}
        super().__init__(attrs=attrs, format=format)


class AdminDateWidget(BaseAdminDateWidget):
    template_name = "admin/widgets/date.html"


class BaseAdminTimeWidget(forms.TimeInput):
    class Media:
        js = [
            "admin/js/calendar.js",
            "admin/js/admin/DateTimeShortcuts.js",
        ]

    def __init__(self, attrs=None, format=None):
        attrs = {"class": "vTimeField", "size": "8", **(attrs or {})}
        super().__init__(attrs=attrs, format=format)


class AdminTimeWidget(BaseAdminTimeWidget):
    template_name = "admin/widgets/time.html"


class AdminSplitDateTime(forms.SplitDateTimeWidget):
    """
    A SplitDateTime Widget that has some admin-specific styling.
    """

    template_name = "admin/widgets/split_datetime.html"

    def __init__(self, attrs=None):
        widgets = [BaseAdminDateWidget, BaseAdminTimeWidget]
        # Note that we're calling MultiWidget, not SplitDateTimeWidget, because
        # we want to define widgets.
        forms.MultiWidget.__init__(self, widgets, attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["date_label"] = _("Date:")
        context["time_label"] = _("Time:")
        return context


class AdminRadioSelect(forms.RadioSelect):
    template_name = "admin/widgets/radio.html"


class AdminFileWidget(forms.ClearableFileInput):
    template_name = "admin/widgets/clearable_file_input.html"


def url_params_from_lookup_dict(lookups):
    """
    Converts a lookup dictionary to a dictionary of query parameters, handling various data types and callable values, making it suitable for use in URL queries.
    """
    params = {}
    if lookups and hasattr(lookups, "items"):
        for k, v in lookups.items():
            if callable(v):
                v = v()
            if isinstance(v, (tuple, list)):
                v = ",".join(str(x) for x in v)
            elif isinstance(v, bool):
                v = ("0", "1")[v]
            else:
                v = str(v)
            params[k] = v
    return params


class ForeignKeyRawIdWidget(forms.TextInput):
    """
    A Widget for displaying ForeignKeys in the "raw_id" interface rather than
    in a <select> box.
    """

    template_name = "admin/widgets/foreign_key_raw_id.html"

    def __init__(self, rel, admin_site, attrs=None, using=None):
        self.rel = rel
        self.admin_site = admin_site
        self.db = using
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        """
        Returns a dictionary of context variables used to render a field in the Django admin interface.
        It extends the field context by adding related model lookup URL and customizing the widget CSS class.
        If the related model is registered in the admin site, it also includes a link to the changelist view of the related model.
        """
        context = super().get_context(name, value, attrs)
        rel_to = self.rel.model
        if self.admin_site.is_registered(rel_to):
            # The related object is registered with the same AdminSite
            related_url = reverse(
                "admin:%s_%s_changelist"
                % (
                    rel_to._meta.app_label,
                    rel_to._meta.model_name,
                ),
                current_app=self.admin_site.name,
            )

            params = self.url_parameters()
            if params:
                related_url += "?" + urlencode(params)
            context["related_url"] = related_url
            context["link_title"] = _("Lookup")
            # The JavaScript code looks for this class.
            css_class = "vForeignKeyRawIdAdminField"
            if isinstance(self.rel.get_related_field(), UUIDField):
                css_class += " vUUIDField"
            context["widget"]["attrs"].setdefault("class", css_class)
        else:
            context["related_url"] = None
        if context["widget"]["value"]:
            context["link_label"], context["link_url"] = self.label_and_url_for_value(
                value
            )
        else:
            context["link_label"] = None
        return context

    def base_url_parameters(self):
        limit_choices_to = self.rel.limit_choices_to
        if callable(limit_choices_to):
            limit_choices_to = limit_choices_to()
        return url_params_from_lookup_dict(limit_choices_to)

    def url_parameters(self):
        from django.contrib.admin.views.main import TO_FIELD_VAR

        params = self.base_url_parameters()
        params.update({TO_FIELD_VAR: self.rel.get_related_field().name})
        return params

    def label_and_url_for_value(self, value):
        """
        Returns a tuple containing a label and URL for a given value related to this model.

        The label is a truncated string representation of the related object, and the URL
        is a link to the change view for that object in the admin interface, if available.

        Args:
            value: The value for which to retrieve the related object.

        Returns:
            tuple: A tuple containing the label and URL.

        """
        key = self.rel.get_related_field().name
        try:
            obj = self.rel.model._default_manager.using(self.db).get(**{key: value})
        except (ValueError, self.rel.model.DoesNotExist, ValidationError):
            return "", ""

        try:
            url = reverse(
                "%s:%s_%s_change"
                % (
                    self.admin_site.name,
                    obj._meta.app_label,
                    obj._meta.model_name,
                ),
                args=(obj.pk,),
            )
        except NoReverseMatch:
            url = ""  # Admin not registered for target model.

        return Truncator(obj).words(14), url


class ManyToManyRawIdWidget(ForeignKeyRawIdWidget):
    """
    A Widget for displaying ManyToMany ids in the "raw_id" interface rather than
    in a <select multiple> box.
    """

    template_name = "admin/widgets/many_to_many_raw_id.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if self.admin_site.is_registered(self.rel.model):
            # The related object is registered with the same AdminSite
            context["widget"]["attrs"]["class"] = "vManyToManyRawIdAdminField"
        return context

    def url_parameters(self):
        return self.base_url_parameters()

    def label_and_url_for_value(self, value):
        return "", ""

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if value:
            return value.split(",")

    def format_value(self, value):
        return ",".join(str(v) for v in value) if value else ""


class RelatedFieldWidgetWrapper(forms.Widget):
    """
    This class is a wrapper to a given widget to add the add icon for the
    admin interface.
    """

    template_name = "admin/widgets/related_widget_wrapper.html"

    def __init__(
        self,
        widget,
        rel,
        admin_site,
        can_add_related=None,
        can_change_related=False,
        can_delete_related=False,
        can_view_related=False,
    ):
        """

        Initialize the related object representation for the admin interface.

        This constructor sets up the necessary attributes for displaying and interacting with
        related objects in the admin interface, including permissions for adding, changing,
        deleting, and viewing related objects.

        :param widget: The widget used to represent the related object.
        :param rel: The relationship between the current model and the related model.
        :param admin_site: The admin site instance.
        :param can_add_related: Whether related objects can be added. Defaults to None.
        :param can_change_related: Whether related objects can be changed. Defaults to False.
        :param can_delete_related: Whether related objects can be deleted. Defaults to False.
        :param can_view_related: Whether related objects can be viewed. Defaults to False.

        """
        self.needs_multipart_form = widget.needs_multipart_form
        self.attrs = widget.attrs
        self.widget = widget
        self.rel = rel
        # Backwards compatible check for whether a user can add related
        # objects.
        if can_add_related is None:
            can_add_related = admin_site.is_registered(rel.model)
        self.can_add_related = can_add_related
        # XXX: The UX does not support multiple selected values.
        multiple = getattr(widget, "allow_multiple_selected", False)
        if not isinstance(widget, AutocompleteMixin):
            self.attrs["data-context"] = "available-source"
        self.can_change_related = not multiple and can_change_related
        # XXX: The deletion UX can be confusing when dealing with cascading deletion.
        cascade = getattr(rel, "on_delete", None) is CASCADE
        self.can_delete_related = not multiple and not cascade and can_delete_related
        self.can_view_related = not multiple and can_view_related
        # so we can check if the related object is registered with this AdminSite
        self.admin_site = admin_site

    def __deepcopy__(self, memo):
        """
        Custom implementation of the deepcopy protocol to create a deep copy of the object.

         Copies the widget instance and attribute dictionary while preserving unique identities.

         :param memo: A dictionary mapping id(object) to copy of object used to avoid infinite recursion.
         :return: A new copy of the object with deep-copied widget and shared attributes
        """
        obj = copy.copy(self)
        obj.widget = copy.deepcopy(self.widget, memo)
        obj.attrs = self.widget.attrs
        memo[id(self)] = obj
        return obj

    @property
    def is_hidden(self):
        return self.widget.is_hidden

    @property
    def media(self):
        return self.widget.media

    @property
    def choices(self):
        return self.widget.choices

    @choices.setter
    def choices(self, value):
        self.widget.choices = value

    def get_related_url(self, info, action, *args):
        return reverse(
            "admin:%s_%s_%s" % (info + (action,)),
            current_app=self.admin_site.name,
            args=args,
        )

    def get_context(self, name, value, attrs):
        """
        Returns a dictionary containing the context for rendering a related model field in the Django admin interface, including the rendered widget, URLs for adding, changing, and deleting related objects, and flags indicating the availability of these actions.
        """
        from django.contrib.admin.views.main import IS_POPUP_VAR, TO_FIELD_VAR

        rel_opts = self.rel.model._meta
        info = (rel_opts.app_label, rel_opts.model_name)
        related_field_name = self.rel.get_related_field().name
        url_params = "&".join(
            "%s=%s" % param
            for param in [
                (TO_FIELD_VAR, related_field_name),
                (IS_POPUP_VAR, 1),
            ]
        )
        context = {
            "rendered_widget": self.widget.render(name, value, attrs),
            "is_hidden": self.is_hidden,
            "name": name,
            "url_params": url_params,
            "model": rel_opts.verbose_name,
            "model_name": rel_opts.model_name,
            "can_add_related": self.can_add_related,
            "can_change_related": self.can_change_related,
            "can_delete_related": self.can_delete_related,
            "can_view_related": self.can_view_related,
            "model_has_limit_choices_to": self.rel.limit_choices_to,
        }
        if self.can_add_related:
            context["add_related_url"] = self.get_related_url(info, "add")
        if self.can_delete_related:
            context["delete_related_template_url"] = self.get_related_url(
                info, "delete", "__fk__"
            )
        if self.can_view_related or self.can_change_related:
            context["view_related_url_params"] = f"{TO_FIELD_VAR}={related_field_name}"
            context["change_related_template_url"] = self.get_related_url(
                info, "change", "__fk__"
            )
        return context

    def value_from_datadict(self, data, files, name):
        return self.widget.value_from_datadict(data, files, name)

    def value_omitted_from_data(self, data, files, name):
        return self.widget.value_omitted_from_data(data, files, name)

    def id_for_label(self, id_):
        return self.widget.id_for_label(id_)


class AdminTextareaWidget(forms.Textarea):
    def __init__(self, attrs=None):
        super().__init__(attrs={"class": "vLargeTextField", **(attrs or {})})


class AdminTextInputWidget(forms.TextInput):
    def __init__(self, attrs=None):
        super().__init__(attrs={"class": "vTextField", **(attrs or {})})


class AdminEmailInputWidget(forms.EmailInput):
    def __init__(self, attrs=None):
        super().__init__(attrs={"class": "vTextField", **(attrs or {})})


class AdminURLFieldWidget(forms.URLInput):
    template_name = "admin/widgets/url.html"

    def __init__(self, attrs=None, validator_class=URLValidator):
        super().__init__(attrs={"class": "vURLField", **(attrs or {})})
        self.validator = validator_class()

    def get_context(self, name, value, attrs):
        """

        Returns the context for a URL widget, including validation status and localized labels.

        The context includes the current and change labels, a formatted href attribute for the widget,
        and a boolean indicating whether the provided URL is valid.

        :param name: The name of the widget.
        :param value: The current value of the widget.
        :param attrs: Additional attributes for the widget.
        :returns: A dictionary containing the widget context.

        """
        try:
            self.validator(value if value else "")
            url_valid = True
        except ValidationError:
            url_valid = False
        context = super().get_context(name, value, attrs)
        context["current_label"] = _("Currently:")
        context["change_label"] = _("Change:")
        context["widget"]["href"] = (
            smart_urlquote(context["widget"]["value"]) if value else ""
        )
        context["url_valid"] = url_valid
        return context


class AdminIntegerFieldWidget(forms.NumberInput):
    class_name = "vIntegerField"

    def __init__(self, attrs=None):
        super().__init__(attrs={"class": self.class_name, **(attrs or {})})


class AdminBigIntegerFieldWidget(AdminIntegerFieldWidget):
    class_name = "vBigIntegerField"


class AdminUUIDInputWidget(forms.TextInput):
    def __init__(self, attrs=None):
        super().__init__(attrs={"class": "vUUIDField", **(attrs or {})})


# Mapping of lowercase language codes [returned by Django's get_language()] to
# language codes supported by select2.
# See django/contrib/admin/static/admin/js/vendor/select2/i18n/*
SELECT2_TRANSLATIONS = {
    x.lower(): x
    for x in [
        "ar",
        "az",
        "bg",
        "ca",
        "cs",
        "da",
        "de",
        "el",
        "en",
        "es",
        "et",
        "eu",
        "fa",
        "fi",
        "fr",
        "gl",
        "he",
        "hi",
        "hr",
        "hu",
        "id",
        "is",
        "it",
        "ja",
        "km",
        "ko",
        "lt",
        "lv",
        "mk",
        "ms",
        "nb",
        "nl",
        "pl",
        "pt-BR",
        "pt",
        "ro",
        "ru",
        "sk",
        "sr-Cyrl",
        "sr",
        "sv",
        "th",
        "tr",
        "uk",
        "vi",
    ]
}
SELECT2_TRANSLATIONS.update({"zh-hans": "zh-CN", "zh-hant": "zh-TW"})


def get_select2_language():
    """
    Returns the select2 language code for the current language, 
    falling back to a supported language variant if the exact language is not supported.
    """
    lang_code = get_language()
    supported_code = SELECT2_TRANSLATIONS.get(lang_code)
    if supported_code is None and lang_code is not None:
        # If 'zh-hant-tw' is not supported, try subsequent language codes i.e.
        # 'zh-hant' and 'zh'.
        i = None
        while (i := lang_code.rfind("-", 0, i)) > -1:
            if supported_code := SELECT2_TRANSLATIONS.get(lang_code[:i]):
                return supported_code
    return supported_code


class AutocompleteMixin:
    """
    Select widget mixin that loads options from AutocompleteJsonView via AJAX.

    Renders the necessary data attributes for select2 and adds the static form
    media.
    """

    url_name = "%s:autocomplete"

    def __init__(self, field, admin_site, attrs=None, choices=(), using=None):
        """
        Initializes a form field for use in an admin interface, providing configuration for database interaction, display attributes, and choice options.
        """
        self.field = field
        self.admin_site = admin_site
        self.db = using
        self.choices = choices
        self.attrs = {} if attrs is None else attrs.copy()
        self.i18n_name = get_select2_language()

    def get_url(self):
        return reverse(self.url_name % self.admin_site.name)

    def build_attrs(self, base_attrs, extra_attrs=None):
        """
        Sets the HTML attributes required for select2's AJAX functionality, including data attributes for caching, delay, request type, and URL, as well as metadata about the related model and field.
        """
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        attrs.setdefault("class", "")
        attrs.update(
            {
                "data-ajax--cache": "true",
                "data-ajax--delay": 250,
                "data-ajax--type": "GET",
                "data-ajax--url": self.get_url(),
                "data-app-label": self.field.model._meta.app_label,
                "data-model-name": self.field.model._meta.model_name,
                "data-field-name": self.field.name,
                "data-theme": "admin-autocomplete",
                "data-allow-clear": json.dumps(not self.is_required),
                "data-placeholder": "",  # Allows clearing of the input.
                "lang": self.i18n_name,
                "class": attrs["class"]
                + (" " if attrs["class"] else "")
                + "admin-autocomplete",
            }
        )
        return attrs

    def optgroups(self, name, value, attr=None):
        """
        Return the options for a select input field, based on the provided name, value, and optional attributes.

        Handles the construction of option groups, including the creation of empty or default options, and the selection of options based on the provided value.

        The function takes into account various field properties, such as whether the field is required or if multiple selections are allowed, to determine the correct options to display.

        Returns a list of option groups, where each group contains a tuple of (group name, options, index).
        """
        default = (None, [], 0)
        groups = [default]
        has_selected = False
        selected_choices = {
            str(v) for v in value if str(v) not in self.choices.field.empty_values
        }
        if not self.is_required and not self.allow_multiple_selected:
            default[1].append(self.create_option(name, "", "", False, 0))
        remote_model_opts = self.field.remote_field.model._meta
        to_field_name = getattr(
            self.field.remote_field, "field_name", remote_model_opts.pk.attname
        )
        to_field_name = remote_model_opts.get_field(to_field_name).attname
        choices = (
            (getattr(obj, to_field_name), self.choices.field.label_from_instance(obj))
            for obj in self.choices.queryset.using(self.db).filter(
                **{"%s__in" % to_field_name: selected_choices}
            )
        )
        for option_value, option_label in choices:
            selected = str(option_value) in value and (
                has_selected is False or self.allow_multiple_selected
            )
            has_selected |= selected
            index = len(default[1])
            subgroup = default[1]
            subgroup.append(
                self.create_option(
                    name, option_value, option_label, selected_choices, index
                )
            )
        return groups

    @property
    def media(self):
        extra = "" if settings.DEBUG else ".min"
        i18n_file = (
            ("admin/js/vendor/select2/i18n/%s.js" % self.i18n_name,)
            if self.i18n_name
            else ()
        )
        return forms.Media(
            js=(
                "admin/js/vendor/jquery/jquery%s.js" % extra,
                "admin/js/vendor/select2/select2.full%s.js" % extra,
            )
            + i18n_file
            + (
                "admin/js/jquery.init.js",
                "admin/js/autocomplete.js",
            ),
            css={
                "screen": (
                    "admin/css/vendor/select2/select2%s.css" % extra,
                    "admin/css/autocomplete.css",
                ),
            },
        )


class AutocompleteSelect(AutocompleteMixin, forms.Select):
    pass


class AutocompleteSelectMultiple(AutocompleteMixin, forms.SelectMultiple):
    pass
