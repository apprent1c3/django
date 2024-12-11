from types import NoneType

from django.conf import settings
from django.core.checks import Error


def check_site_id(app_configs, **kwargs):
    """
    Checks the SITE_ID setting for validity.

    The SITE_ID setting is verified to ensure it is an integer value. If the setting exists and is not an integer, an error is raised.

    :returns: A list of errors if the SITE_ID setting is invalid, otherwise an empty list.
    :raises: None
    :rtype: list[Error]
    """
    if hasattr(settings, "SITE_ID") and not isinstance(
        settings.SITE_ID, (NoneType, int)
    ):
        return [
            Error("The SITE_ID setting must be an integer", id="sites.E101"),
        ]
    return []
