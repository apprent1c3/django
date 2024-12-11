from django.conf import settings

from .. import Error, Tags, register


@register(Tags.compatibility)
def check_csrf_trusted_origins(app_configs, **kwargs):
    """
    Checks if the CSRF_TRUSTED_ORIGINS setting is compatible with Django 4.0.

    Validates each origin in the CSRF_TRUSTED_ORIGINS setting to ensure it starts with a scheme (usually http:// or https://). 
    If an origin without a scheme is found, an error is reported with instructions for correction. 

    Returns a list of errors found during the validation process.
    """
    errors = []
    for origin in settings.CSRF_TRUSTED_ORIGINS:
        if "://" not in origin:
            errors.append(
                Error(
                    "As of Django 4.0, the values in the CSRF_TRUSTED_ORIGINS "
                    "setting must start with a scheme (usually http:// or "
                    "https://) but found %s. See the release notes for details."
                    % origin,
                    id="4_0.E001",
                )
            )
    return errors
