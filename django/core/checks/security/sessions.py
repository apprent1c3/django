from django.conf import settings

from .. import Tags, Warning, register


def add_session_cookie_message(message):
    return message + (
        " Using a secure-only session cookie makes it more difficult for "
        "network traffic sniffers to hijack user sessions."
    )


W010 = Warning(
    add_session_cookie_message(
        "You have 'django.contrib.sessions' in your INSTALLED_APPS, "
        "but you have not set SESSION_COOKIE_SECURE to True."
    ),
    id="security.W010",
)

W011 = Warning(
    add_session_cookie_message(
        "You have 'django.contrib.sessions.middleware.SessionMiddleware' "
        "in your MIDDLEWARE, but you have not set "
        "SESSION_COOKIE_SECURE to True."
    ),
    id="security.W011",
)

W012 = Warning(
    add_session_cookie_message("SESSION_COOKIE_SECURE is not set to True."),
    id="security.W012",
)


def add_httponly_message(message):
    return message + (
        " Using an HttpOnly session cookie makes it more difficult for "
        "cross-site scripting attacks to hijack user sessions."
    )


W013 = Warning(
    add_httponly_message(
        "You have 'django.contrib.sessions' in your INSTALLED_APPS, "
        "but you have not set SESSION_COOKIE_HTTPONLY to True.",
    ),
    id="security.W013",
)

W014 = Warning(
    add_httponly_message(
        "You have 'django.contrib.sessions.middleware.SessionMiddleware' "
        "in your MIDDLEWARE, but you have not set "
        "SESSION_COOKIE_HTTPONLY to True."
    ),
    id="security.W014",
)

W015 = Warning(
    add_httponly_message("SESSION_COOKIE_HTTPONLY is not set to True."),
    id="security.W015",
)


@register(Tags.security, deploy=True)
def check_session_cookie_secure(app_configs, **kwargs):
    """
    Checks if the session cookie is set to secure mode in the application configuration.

    This security check verifies the value of ``SESSION_COOKIE_SECURE`` setting to ensure 
    it's set to ``True``, which is recommended to prevent session cookies from being 
    transmitted over an insecure protocol (e.g., HTTP).

    The check also examines the application's configuration to identify potential 
    vulnerabilities related to session management, including the presence of certain 
    session-related applications and middleware.

    If the check finds any issues, it returns a list of error codes (``W010``, ``W011``, 
    or ``W012``) indicating the specific problems detected. If the session cookie is 
    correctly configured, an empty list is returned.
    """
    if settings.SESSION_COOKIE_SECURE is True:
        return []
    errors = []
    if _session_app():
        errors.append(W010)
    if _session_middleware():
        errors.append(W011)
    if len(errors) > 1:
        errors = [W012]
    return errors


@register(Tags.security, deploy=True)
def check_session_cookie_httponly(app_configs, **kwargs):
    if settings.SESSION_COOKIE_HTTPONLY is True:
        return []
    errors = []
    if _session_app():
        errors.append(W013)
    if _session_middleware():
        errors.append(W014)
    if len(errors) > 1:
        errors = [W015]
    return errors


def _session_middleware():
    return "django.contrib.sessions.middleware.SessionMiddleware" in settings.MIDDLEWARE


def _session_app():
    return "django.contrib.sessions" in settings.INSTALLED_APPS
