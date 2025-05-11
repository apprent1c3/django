from django.conf import STATICFILES_STORAGE_ALIAS, settings
from django.contrib.staticfiles.finders import get_finders
from django.core.checks import Error

E005 = Error(
    f"The STORAGES setting must define a '{STATICFILES_STORAGE_ALIAS}' storage.",
    id="staticfiles.E005",
)


def check_finders(app_configs=None, **kwargs):
    """

    Checks all registered static files finders for potential issues.

    Returns a list of errors found by the finders. This check can be useful for 
    identifying and debugging problems with static file configuration.

    :param app_configs: Optional application configurations.
    :param kwargs: Additional keyword arguments.
    :return: A list of errors found by the finders.

    """
    errors = []
    for finder in get_finders():
        try:
            finder_errors = finder.check()
        except NotImplementedError:
            pass
        else:
            errors.extend(finder_errors)
    return errors


def check_storages(app_configs=None, **kwargs):
    """
    Checks if the staticfiles storage is defined in the project's STORAGES setting, returning a list of errors if it's not configured properly.
    """
    errors = []
    if STATICFILES_STORAGE_ALIAS not in settings.STORAGES:
        errors.append(E005)
    return errors
