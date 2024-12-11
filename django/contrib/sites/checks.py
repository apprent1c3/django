from types import NoneType

from django.conf import settings
from django.core.checks import Error


def check_site_id(app_configs, **kwargs):
    """
    Checks the SITE_ID setting for validity.

    This function verifies that the SITE_ID setting is either an integer or None. If the setting is present but not of the correct type, it returns a list of errors indicating the problem with the SITE_ID setting. If the setting is valid or missing, it returns an empty list.
    """
    if hasattr(settings, "SITE_ID") and not isinstance(
        settings.SITE_ID, (NoneType, int)
    ):
        return [
            Error("The SITE_ID setting must be an integer", id="sites.E101"),
        ]
    return []
