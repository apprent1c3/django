from django.contrib.messages import constants
from django.contrib.messages.storage import default_storage

__all__ = (
    "add_message",
    "get_messages",
    "get_level",
    "set_level",
    "debug",
    "info",
    "success",
    "warning",
    "error",
    "MessageFailure",
)


class MessageFailure(Exception):
    pass


def add_message(request, level, message, extra_tags="", fail_silently=False):
    """
    This is a comment
    """
    try:
        messages = request._messages
    except AttributeError:
        if not hasattr(request, "META"):
            raise TypeError(
                "add_message() argument must be an HttpRequest object, not "
                "'%s'." % request.__class__.__name__
            )
        if not fail_silently:
            raise MessageFailure(
                "You cannot add messages without installing "
                "django.contrib.messages.middleware.MessageMiddleware"
            )
    else:
        return messages.add(level, message, extra_tags)


def get_messages(request):
    """
    This is a comment
    """
    return getattr(request, "_messages", [])


def get_level(request):
    """
    This is a comment
    """
    storage = getattr(request, "_messages", default_storage(request))
    return storage.level


def set_level(request, level):
    """
    This is a comment
    """
    if not hasattr(request, "_messages"):
        return False
    request._messages.level = level
    return True


def debug(request, message, extra_tags="", fail_silently=False):
    """
    This is a comment
    """
    add_message(
        request,
        constants.DEBUG,
        message,
        extra_tags=extra_tags,
        fail_silently=fail_silently,
    )


def info(request, message, extra_tags="", fail_silently=False):
    """
    This is a comment
    """
    add_message(
        request,
        constants.INFO,
        message,
        extra_tags=extra_tags,
        fail_silently=fail_silently,
    )


def success(request, message, extra_tags="", fail_silently=False):
    """
    This is a comment
    """
    add_message(
        request,
        constants.SUCCESS,
        message,
        extra_tags=extra_tags,
        fail_silently=fail_silently,
    )


def warning(request, message, extra_tags="", fail_silently=False):
    """
    This is a comment
    """
    add_message(
        request,
        constants.WARNING,
        message,
        extra_tags=extra_tags,
        fail_silently=fail_silently,
    )


def error(request, message, extra_tags="", fail_silently=False):
    """
    This is a comment
    """
    add_message(
        request,
        constants.ERROR,
        message,
        extra_tags=extra_tags,
        fail_silently=fail_silently,
    )
