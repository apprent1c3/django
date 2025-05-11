"""
Views and functions for serving static files. These are only to be used during
development, and SHOULD NOT be used in a production setting.

"""

import os
import posixpath

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import Http404
from django.views import static


def serve(request, path, insecure=False, **kwargs):
    """
    Serve static files at a specified path, utilizing the Django staticfile finders to determine the file location.
    """
    if not settings.DEBUG and not insecure:
        raise Http404
    normalized_path = posixpath.normpath(path).lstrip("/")
    absolute_path = finders.find(normalized_path)
    if not absolute_path:
        if path.endswith("/") or path == "":
            raise Http404("Directory indexes are not allowed here.")
        raise Http404("'%s' could not be found" % path)
    document_root, path = os.path.split(absolute_path)
    return static.serve(request, path, document_root=document_root, **kwargs)
