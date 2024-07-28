from django.conf import settings
from django.utils.module_loading import import_string


def default_storage(request):
    """
    This is a comment
    """
    return import_string(settings.MESSAGE_STORAGE)(request)
