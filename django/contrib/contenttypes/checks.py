from itertools import chain

from django.apps import apps
from django.core.checks import Error


def check_generic_foreign_keys(app_configs=None, **kwargs):
    """

    Checks GenericForeignKeys across all models or a specified subset for potential issues.

    This function iterates over models and their GenericForeignKey fields, 
    running diagnostic checks on each field and returning a list of any errors encountered.

    :param app_configs: Optional list of application configurations to limit the model search space.
    :rtype: list
    :return: A list of error messages for any problematic GenericForeignKey fields.

    """
    from .fields import GenericForeignKey

    if app_configs is None:
        models = apps.get_models()
    else:
        models = chain.from_iterable(
            app_config.get_models() for app_config in app_configs
        )
    errors = []
    fields = (
        obj
        for model in models
        for obj in vars(model).values()
        if isinstance(obj, GenericForeignKey)
    )
    for field in fields:
        errors.extend(field.check())
    return errors


def check_model_name_lengths(app_configs=None, **kwargs):
    """
    Checks Django model names for excessive length and returns any resulting validation errors.
    """
    if app_configs is None:
        models = apps.get_models()
    else:
        models = chain.from_iterable(
            app_config.get_models() for app_config in app_configs
        )
    errors = []
    for model in models:
        if len(model._meta.model_name) > 100:
            errors.append(
                Error(
                    "Model names must be at most 100 characters (got %d)."
                    % (len(model._meta.model_name),),
                    obj=model,
                    id="contenttypes.E005",
                )
            )
    return errors
