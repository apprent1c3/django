from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.forms import ModelForm, modelformset_factory
from django.forms.models import BaseModelFormSet


class BaseGenericInlineFormSet(BaseModelFormSet):
    """
    A formset for generic inline objects to a parent.
    """

    def __init__(
        self,
        data=None,
        files=None,
        instance=None,
        save_as_new=False,
        prefix=None,
        queryset=None,
        **kwargs,
    ):
        """
        Initializes the form for generic inline editing of a related model instance.

        This constructor sets up the form with a queryset and optional instance, data, files, and prefix. 
        It handles the case where the related instance is new or existing, and optionally saves the 
        related instance as new. The form's queryset is filtered by the content type and primary key 
        of the related instance, if one is provided.
        """
        opts = self.model._meta
        self.instance = instance
        self.rel_name = (
            opts.app_label
            + "-"
            + opts.model_name
            + "-"
            + self.ct_field.name
            + "-"
            + self.ct_fk_field.name
        )
        self.save_as_new = save_as_new
        if self.instance is None or self.instance.pk is None:
            qs = self.model._default_manager.none()
        else:
            if queryset is None:
                queryset = self.model._default_manager
            qs = queryset.filter(
                **{
                    self.ct_field.name: ContentType.objects.get_for_model(
                        self.instance, for_concrete_model=self.for_concrete_model
                    ),
                    self.ct_fk_field.name: self.instance.pk,
                }
            )
        super().__init__(queryset=qs, data=data, files=files, prefix=prefix, **kwargs)

    def initial_form_count(self):
        if self.save_as_new:
            return 0
        return super().initial_form_count()

    @classmethod
    def get_default_prefix(cls):
        opts = cls.model._meta
        return (
            opts.app_label
            + "-"
            + opts.model_name
            + "-"
            + cls.ct_field.name
            + "-"
            + cls.ct_fk_field.name
        )

    def save_new(self, form, commit=True):
        setattr(
            form.instance,
            self.ct_field.attname,
            ContentType.objects.get_for_model(self.instance).pk,
        )
        setattr(form.instance, self.ct_fk_field.attname, self.instance.pk)
        return form.save(commit=commit)


def generic_inlineformset_factory(
    model,
    form=ModelForm,
    formset=BaseGenericInlineFormSet,
    ct_field="content_type",
    fk_field="object_id",
    fields=None,
    exclude=None,
    extra=3,
    can_order=False,
    can_delete=True,
    max_num=None,
    formfield_callback=None,
    validate_max=False,
    for_concrete_model=True,
    min_num=None,
    validate_min=False,
    absolute_max=None,
    can_delete_extra=True,
):
    """
    Creates a GenericInlineFormSet class for the given model, 
    enabling the creation of forms for generic foreign keys.

    :param model: The model that the formset will be for.
    :param form: The form class to use (defaults to ModelForm).
    :param formset: The formset class to use (defaults to BaseGenericInlineFormSet).
    :param ct_field: The field on the model that represents the content type.
    :param fk_field: The field on the model that represents the object ID.
    :param fields: A list of field names to include in the form. Defaults to None.
    :param exclude: A list of field names to exclude from the form. Defaults to None.
    :param extra: The number of extra forms to display. Defaults to 3.
    :param can_order: Whether the forms can be ordered. Defaults to False.
    :param can_delete: Whether the forms can be deleted. Defaults to True.
    :param max_num: The maximum number of forms. Defaults to None.
    :param formfield_callback: A callback function to modify form fields. Defaults to None.
    :param validate_max: Whether to validate the maximum number of forms. Defaults to False.
    :param for_concrete_model: Whether the formset is for a concrete model. Defaults to True.
    :param min_num: The minimum number of forms. Defaults to None.
    :param validate_min: Whether to validate the minimum number of forms. Defaults to False.
    :param absolute_max: The absolute maximum number of forms. Defaults to None.
    :param can_delete_extra: Whether extra forms can be deleted. Defaults to True.

    :return: A GenericInlineFormSet class for the given model and options.
    """
    opts = model._meta
    # if there is no field called `ct_field` let the exception propagate
    ct_field = opts.get_field(ct_field)
    if (
        not isinstance(ct_field, models.ForeignKey)
        or ct_field.remote_field.model != ContentType
    ):
        raise Exception("fk_name '%s' is not a ForeignKey to ContentType" % ct_field)
    fk_field = opts.get_field(fk_field)  # let the exception propagate
    exclude = [*(exclude or []), ct_field.name, fk_field.name]
    FormSet = modelformset_factory(
        model,
        form=form,
        formfield_callback=formfield_callback,
        formset=formset,
        extra=extra,
        can_delete=can_delete,
        can_order=can_order,
        fields=fields,
        exclude=exclude,
        max_num=max_num,
        validate_max=validate_max,
        min_num=min_num,
        validate_min=validate_min,
        absolute_max=absolute_max,
        can_delete_extra=can_delete_extra,
    )
    FormSet.ct_field = ct_field
    FormSet.ct_fk_field = fk_field
    FormSet.for_concrete_model = for_concrete_model
    return FormSet
