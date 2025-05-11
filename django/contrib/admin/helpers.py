import json

from django import forms
from django.contrib.admin.utils import (
    display_for_field,
    flatten_fieldsets,
    help_text_for_field,
    label_for_field,
    lookup_field,
    quote,
)
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.fields.related import (
    ForeignObjectRel,
    ManyToManyRel,
    OneToOneField,
)
from django.forms.utils import flatatt
from django.template.defaultfilters import capfirst, linebreaksbr
from django.urls import NoReverseMatch, reverse
from django.utils.functional import cached_property
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

ACTION_CHECKBOX_NAME = "_selected_action"


class ActionForm(forms.Form):
    action = forms.ChoiceField(label=_("Action:"))
    select_across = forms.BooleanField(
        label="",
        required=False,
        initial=0,
        widget=forms.HiddenInput({"class": "select-across"}),
    )


class AdminForm:
    def __init__(
        self,
        form,
        fieldsets,
        prepopulated_fields,
        readonly_fields=None,
        model_admin=None,
    ):
        """

        Initializes the instance with form and field configuration.

        : param form: The form instance to be used.
        : param fieldsets: Fieldsets for the form.
        : param prepopulated_fields: Dictionary of fields to be prepopulated with dependencies.
        : param readonly_fields: Optional list of fields to be marked as read-only, defaults to None.
        : param model_admin: Optional model admin instance.

        """
        self.form, self.fieldsets = form, fieldsets
        self.prepopulated_fields = [
            {"field": form[field_name], "dependencies": [form[f] for f in dependencies]}
            for field_name, dependencies in prepopulated_fields.items()
        ]
        self.model_admin = model_admin
        if readonly_fields is None:
            readonly_fields = ()
        self.readonly_fields = readonly_fields

    def __repr__(self):
        return (
            f"<{self.__class__.__qualname__}: "
            f"form={self.form.__class__.__qualname__} "
            f"fieldsets={self.fieldsets!r}>"
        )

    def __iter__(self):
        for name, options in self.fieldsets:
            yield Fieldset(
                self.form,
                name,
                readonly_fields=self.readonly_fields,
                model_admin=self.model_admin,
                **options,
            )

    @property
    def errors(self):
        return self.form.errors

    @property
    def non_field_errors(self):
        return self.form.non_field_errors

    @property
    def fields(self):
        return self.form.fields

    @property
    def is_bound(self):
        return self.form.is_bound

    @property
    def media(self):
        media = self.form.media
        for fs in self:
            media += fs.media
        return media


class Fieldset:
    def __init__(
        self,
        form,
        name=None,
        readonly_fields=(),
        fields=(),
        classes=(),
        description=None,
        model_admin=None,
    ):
        """

        Initializes a form layout component.

        :param form: The form associated with this layout.
        :param name: The name of the layout.
        :param readonly_fields: Fields that should be displayed as read-only.
        :param fields: The fields to be included in the layout.
        :param classes: CSS classes to apply to the layout.
        :param description: A brief description of the layout.
        :param model_admin: The model admin instance associated with this layout.

        """
        self.form = form
        self.name, self.fields = name, fields
        self.classes = " ".join(classes)
        self.description = description
        self.model_admin = model_admin
        self.readonly_fields = readonly_fields

    @property
    def media(self):
        return forms.Media()

    @cached_property
    def is_collapsible(self):
        if any([field in self.fields for field in self.form.errors]):
            return False
        return "collapse" in self.classes

    def __iter__(self):
        for field in self.fields:
            yield Fieldline(
                self.form, field, self.readonly_fields, model_admin=self.model_admin
            )


class Fieldline:
    def __init__(self, form, field, readonly_fields=None, model_admin=None):
        """
        Initializes an instance, specifying a form, field(s), and optionally readonly fields and a model admin.

            This constructor sets up the basic properties of the instance, including the associated form, fields to be managed,
            and fields that should be displayed as read-only. It determines whether any of the fields are visible, meaning not hidden.

        """
        self.form = form  # A django.forms.Form instance
        if not hasattr(field, "__iter__") or isinstance(field, str):
            self.fields = [field]
        else:
            self.fields = field
        self.has_visible_field = not all(
            field in self.form.fields and self.form.fields[field].widget.is_hidden
            for field in self.fields
        )
        self.model_admin = model_admin
        if readonly_fields is None:
            readonly_fields = ()
        self.readonly_fields = readonly_fields

    def __iter__(self):
        """
        Returns an iterator over the form fields, yielding :class:`AdminField` or :class:`AdminReadonlyField` instances depending on whether each field is read-only or not.
        """
        for i, field in enumerate(self.fields):
            if field in self.readonly_fields:
                yield AdminReadonlyField(
                    self.form, field, is_first=(i == 0), model_admin=self.model_admin
                )
            else:
                yield AdminField(self.form, field, is_first=(i == 0))

    def errors(self):
        return mark_safe(
            "\n".join(
                self.form[f].errors.as_ul()
                for f in self.fields
                if f not in self.readonly_fields
            ).strip("\n")
        )


class AdminField:
    def __init__(self, form, field, is_first):
        self.field = form[field]  # A django.forms.BoundField instance
        self.is_first = is_first  # Whether this field is first on the line
        self.is_checkbox = isinstance(self.field.field.widget, forms.CheckboxInput)
        self.is_readonly = False

    def label_tag(self):
        """
        Generates an HTML label tag for the field, customizing the tag based on the field's requirements and the current rendering context, such as whether it's a checkbox or if it's the first field.
        """
        classes = []
        contents = conditional_escape(self.field.label)
        if self.is_checkbox:
            classes.append("vCheckboxLabel")

        if self.field.field.required:
            classes.append("required")
        if not self.is_first:
            classes.append("inline")
        attrs = {"class": " ".join(classes)} if classes else {}
        # checkboxes should not have a label suffix as the checkbox appears
        # to the left of the label.
        return self.field.label_tag(
            contents=mark_safe(contents),
            attrs=attrs,
            label_suffix="" if self.is_checkbox else None,
        )

    def errors(self):
        return mark_safe(self.field.errors.as_ul())


class AdminReadonlyField:
    def __init__(self, form, field, is_first, model_admin=None):
        # Make self.field look a little bit like a field. This means that
        # {{ field.name }} must be a useful class name to identify the field.
        # For convenience, store other field-related data here too.
        """
        Initializes a field representation for a form.

        Stores information about a form field, including its name, label, help text,
        visibility, and other attributes, to facilitate rendering and interaction.
        Optional model administration object provides additional context for label
        and help text resolution.
        """
        if callable(field):
            class_name = field.__name__ if field.__name__ != "<lambda>" else ""
        else:
            class_name = field

        if form._meta.labels and class_name in form._meta.labels:
            label = form._meta.labels[class_name]
        else:
            label = label_for_field(field, form._meta.model, model_admin, form=form)

        if form._meta.help_texts and class_name in form._meta.help_texts:
            help_text = form._meta.help_texts[class_name]
        else:
            help_text = help_text_for_field(class_name, form._meta.model)

        if field in form.fields:
            is_hidden = form.fields[field].widget.is_hidden
        else:
            is_hidden = False

        self.field = {
            "name": class_name,
            "label": label,
            "help_text": help_text,
            "field": field,
            "is_hidden": is_hidden,
        }
        self.form = form
        self.model_admin = model_admin
        self.is_first = is_first
        self.is_checkbox = False
        self.is_readonly = True
        self.empty_value_display = model_admin.get_empty_value_display()

    def label_tag(self):
        """
        Generates an HTML label tag for a form field, optionally applying an \"inline\" class if it's not the first field and including the field's label and suffix.
        """
        attrs = {}
        if not self.is_first:
            attrs["class"] = "inline"
        label = self.field["label"]
        return format_html(
            "<label{}>{}{}</label>",
            flatatt(attrs),
            capfirst(label),
            self.form.label_suffix,
        )

    def get_admin_url(self, remote_field, remote_obj):
        """
        Returns a formatted HTML link to the admin change page for the given remote object, or a string representation of the object if the link cannot be generated.
        """
        url_name = "admin:%s_%s_change" % (
            remote_field.model._meta.app_label,
            remote_field.model._meta.model_name,
        )
        try:
            url = reverse(
                url_name,
                args=[quote(remote_obj.pk)],
                current_app=self.model_admin.admin_site.name,
            )
            return format_html('<a href="{}">{}</a>', url, remote_obj)
        except NoReverseMatch:
            return str(remote_obj)

    def contents(self):
        """

        Returns a rendered representation of a field's value for display in the admin interface.

        This method handles different field types, including boolean, HTML, and foreign key fields,
        and applies the necessary formatting and escaping to ensure safe display.

        """
        from django.contrib.admin.templatetags.admin_list import _boolean_icon

        field, obj, model_admin = (
            self.field["field"],
            self.form.instance,
            self.model_admin,
        )
        try:
            f, attr, value = lookup_field(field, obj, model_admin)
        except (AttributeError, ValueError, ObjectDoesNotExist):
            result_repr = self.empty_value_display
        else:
            if field in self.form.fields:
                widget = self.form[field].field.widget
                # This isn't elegant but suffices for contrib.auth's
                # ReadOnlyPasswordHashWidget.
                if getattr(widget, "read_only", False):
                    return widget.render(field, value)
            if f is None:
                if getattr(attr, "boolean", False):
                    result_repr = _boolean_icon(value)
                else:
                    if hasattr(value, "__html__"):
                        result_repr = value
                    else:
                        result_repr = linebreaksbr(value)
            else:
                if isinstance(f.remote_field, ManyToManyRel) and value is not None:
                    result_repr = ", ".join(map(str, value.all()))
                elif (
                    isinstance(f.remote_field, (ForeignObjectRel, OneToOneField))
                    and value is not None
                ):
                    result_repr = self.get_admin_url(f.remote_field, value)
                else:
                    result_repr = display_for_field(value, f, self.empty_value_display)
                result_repr = linebreaksbr(result_repr)
        return conditional_escape(result_repr)


class InlineAdminFormSet:
    """
    A wrapper around an inline formset for use in the admin system.
    """

    def __init__(
        self,
        inline,
        formset,
        fieldsets,
        prepopulated_fields=None,
        readonly_fields=None,
        model_admin=None,
        has_add_permission=True,
        has_change_permission=True,
        has_delete_permission=True,
        has_view_permission=True,
    ):
        """
        Initializes an inline form instance, setting up the form structure and permissions for editing a related model on an admin page. It combines form configuration, fieldsets arrangement, and permission settings, making it easy to manage inline forms within a Django admin interface.
        """
        self.opts = inline
        self.formset = formset
        self.fieldsets = fieldsets
        self.model_admin = model_admin
        if readonly_fields is None:
            readonly_fields = ()
        self.readonly_fields = readonly_fields
        if prepopulated_fields is None:
            prepopulated_fields = {}
        self.prepopulated_fields = prepopulated_fields
        self.classes = " ".join(inline.classes) if inline.classes else ""
        self.has_add_permission = has_add_permission
        self.has_change_permission = has_change_permission
        self.has_delete_permission = has_delete_permission
        self.has_view_permission = has_view_permission

    def __iter__(self):
        """

        Generates an iterator over inline administration forms.

        Yields InlineAdminForm objects, which provide a way to view and edit related model instances.
        The forms are generated based on the model admin's fieldsets, prepopulated fields, and readonly fields.
        The iterator includes initial forms, extra forms, and an empty form if the user has add permission.

        """
        if self.has_change_permission:
            readonly_fields_for_editing = self.readonly_fields
        else:
            readonly_fields_for_editing = self.readonly_fields + flatten_fieldsets(
                self.fieldsets
            )

        for form, original in zip(
            self.formset.initial_forms, self.formset.get_queryset()
        ):
            view_on_site_url = self.opts.get_view_on_site_url(original)
            yield InlineAdminForm(
                self.formset,
                form,
                self.fieldsets,
                self.prepopulated_fields,
                original,
                readonly_fields_for_editing,
                model_admin=self.opts,
                view_on_site_url=view_on_site_url,
            )
        for form in self.formset.extra_forms:
            yield InlineAdminForm(
                self.formset,
                form,
                self.fieldsets,
                self.prepopulated_fields,
                None,
                self.readonly_fields,
                model_admin=self.opts,
            )
        if self.has_add_permission:
            yield InlineAdminForm(
                self.formset,
                self.formset.empty_form,
                self.fieldsets,
                self.prepopulated_fields,
                None,
                self.readonly_fields,
                model_admin=self.opts,
            )

    def fields(self):
        """
        Returns a generator of dictionaries containing field metadata, such as name, label, widget, required status, and help text, for each field in the formset, taking into account fieldsets, readonly fields, and permission settings.
        """
        fk = getattr(self.formset, "fk", None)
        empty_form = self.formset.empty_form
        meta_labels = empty_form._meta.labels or {}
        meta_help_texts = empty_form._meta.help_texts or {}
        for i, field_name in enumerate(flatten_fieldsets(self.fieldsets)):
            if fk and fk.name == field_name:
                continue
            if not self.has_change_permission or field_name in self.readonly_fields:
                form_field = empty_form.fields.get(field_name)
                widget_is_hidden = False
                if form_field is not None:
                    widget_is_hidden = form_field.widget.is_hidden
                yield {
                    "name": field_name,
                    "label": meta_labels.get(field_name)
                    or label_for_field(
                        field_name,
                        self.opts.model,
                        self.opts,
                        form=empty_form,
                    ),
                    "widget": {"is_hidden": widget_is_hidden},
                    "required": False,
                    "help_text": meta_help_texts.get(field_name)
                    or help_text_for_field(field_name, self.opts.model),
                }
            else:
                form_field = empty_form.fields[field_name]
                label = form_field.label
                if label is None:
                    label = label_for_field(
                        field_name, self.opts.model, self.opts, form=empty_form
                    )
                yield {
                    "name": field_name,
                    "label": label,
                    "widget": form_field.widget,
                    "required": form_field.required,
                    "help_text": form_field.help_text,
                }

    def inline_formset_data(self):
        verbose_name = self.opts.verbose_name
        return json.dumps(
            {
                "name": "#%s" % self.formset.prefix,
                "options": {
                    "prefix": self.formset.prefix,
                    "addText": gettext("Add another %(verbose_name)s")
                    % {
                        "verbose_name": capfirst(verbose_name),
                    },
                    "deleteText": gettext("Remove"),
                },
            }
        )

    @property
    def forms(self):
        return self.formset.forms

    @cached_property
    def is_collapsible(self):
        if any(self.formset.errors):
            return False
        return "collapse" in self.classes

    def non_form_errors(self):
        return self.formset.non_form_errors()

    @property
    def is_bound(self):
        return self.formset.is_bound

    @property
    def total_form_count(self):
        return self.formset.total_form_count

    @property
    def media(self):
        media = self.opts.media + self.formset.media
        for fs in self:
            media += fs.media
        return media


class InlineAdminForm(AdminForm):
    """
    A wrapper around an inline form for use in the admin system.
    """

    def __init__(
        self,
        formset,
        form,
        fieldsets,
        prepopulated_fields,
        original,
        readonly_fields=None,
        model_admin=None,
        view_on_site_url=None,
    ):
        """
        Initializes the admin view for a model instance, setting up the form, fieldsets, and metadata for display and editing.
        """
        self.formset = formset
        self.model_admin = model_admin
        self.original = original
        self.show_url = original and view_on_site_url is not None
        self.absolute_url = view_on_site_url
        super().__init__(
            form, fieldsets, prepopulated_fields, readonly_fields, model_admin
        )

    def __iter__(self):
        for name, options in self.fieldsets:
            yield InlineFieldset(
                self.formset,
                self.form,
                name,
                self.readonly_fields,
                model_admin=self.model_admin,
                **options,
            )

    def needs_explicit_pk_field(self):
        return (
            # Auto fields are editable, so check for auto or non-editable pk.
            self.form._meta.model._meta.auto_field
            or not self.form._meta.model._meta.pk.editable
            # The pk can be editable, but excluded from the inline.
            or (
                self.form._meta.exclude
                and self.form._meta.model._meta.pk.name in self.form._meta.exclude
            )
            or
            # Also search any parents for an auto field. (The pk info is
            # propagated to child models so that does not need to be checked
            # in parents.)
            any(
                parent._meta.auto_field or not parent._meta.model._meta.pk.editable
                for parent in self.form._meta.model._meta.all_parents
            )
        )

    def pk_field(self):
        return AdminField(self.form, self.formset._pk_field.name, False)

    def fk_field(self):
        """
        Returns a foreign key field for the form, if applicable.

            :return: An AdminField instance representing the foreign key field, or an empty string if no foreign key is defined.
            :rtype: AdminField or str
        """
        fk = getattr(self.formset, "fk", None)
        if fk:
            return AdminField(self.form, fk.name, False)
        else:
            return ""

    def deletion_field(self):
        from django.forms.formsets import DELETION_FIELD_NAME

        return AdminField(self.form, DELETION_FIELD_NAME, False)


class InlineFieldset(Fieldset):
    def __init__(self, formset, *args, **kwargs):
        self.formset = formset
        super().__init__(*args, **kwargs)

    def __iter__(self):
        fk = getattr(self.formset, "fk", None)
        for field in self.fields:
            if not fk or fk.name != field:
                yield Fieldline(
                    self.form, field, self.readonly_fields, model_admin=self.model_admin
                )


class AdminErrorList(forms.utils.ErrorList):
    """Store errors for the form/formsets in an add/change view."""

    def __init__(self, form, inline_formsets):
        """
        Initializes the object, initializing the parent class and collecting form validation errors from the provided form and inline formsets.
        """
        super().__init__()

        if form.is_bound:
            self.extend(form.errors.values())
            for inline_formset in inline_formsets:
                self.extend(inline_formset.non_form_errors())
                for errors_in_inline_form in inline_formset.errors:
                    self.extend(errors_in_inline_form.values())
