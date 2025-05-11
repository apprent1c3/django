import re
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import re_path
from django.views.static import serve


def static(prefix, view=serve, **kwargs):
    """

    Serves static files in debug mode by providing a URL pattern.

    Returns a URL pattern to serve files under the given prefix when the application
    is running in debug mode. This is typically used to serve media files from the
    MEDIA_ROOT directory.

    """
    if not prefix:
        raise ImproperlyConfigured("Empty static prefix not permitted")
    elif not settings.DEBUG or urlsplit(prefix).netloc:
        # No-op if not in debug mode or a non-local prefix.
        return []
    return [
        re_path(
            r"^%s(?P<path>.*)$" % re.escape(prefix.lstrip("/")), view, kwargs=kwargs
        ),
    ]
