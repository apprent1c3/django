from django.utils.version import get_version

VERSION = (5, 2, 0, "alpha", 0)

__version__ = get_version(VERSION)


def setup(set_prefix=True):
    """
    Configure the application by setting up settings, logging, and the app registry, and optionally setting the thread-local URL script prefix.
    """
    from django.apps import apps
    from django.conf import settings
    from django.urls import set_script_prefix
    from django.utils.log import configure_logging

    configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)
    if set_prefix:
        set_script_prefix(
            "/" if settings.FORCE_SCRIPT_NAME is None else settings.FORCE_SCRIPT_NAME
        )
    apps.populate(settings.INSTALLED_APPS)
