from itertools import chain

from django.apps import apps
from django.core.checks import Error


def check_generic_foreign_keys(app_configs=None, **kwargs):
    """

    Checks all generic foreign keys in the application's models for potential errors.

    This function iterates over all models in the application (or a specified subset of models)
    and inspects any fields that are instances of GenericForeignKey. It then checks each of these
    fields for errors and returns a list of any issues that are found.

    The function can be run globally across all models in the application, or it can be limited
    to a specific set of models by passing in a list of app configurations.

    Args:
        app_configs (list, optional): A list of application configurations to check. If not provided,
            the function will check all models in the application.

    Returns:
        list: A list of errors found in the generic foreign keys.

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
