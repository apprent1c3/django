from itertools import chain

from django.apps import apps
from django.core.checks import Error


def check_generic_foreign_keys(app_configs=None, **kwargs):
    """
    Checks the integrity of generic foreign key fields across all models in the application.

    It inspects each generic foreign key field to ensure it is correctly configured and reports any errors that are found.

    If application configurations are provided, only models from those applications are checked; otherwise, all models in the application are verified.
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
    Checks if the names of all models in an application exceed the maximum allowed length.

    Takes an optional list of application configurations to check, or all models if none are provided.

    Returns a list of errors for any models with names longer than 100 characters.
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
