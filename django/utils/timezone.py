"""
Timezone-related classes and functions.
"""

import functools
import zoneinfo
from contextlib import ContextDecorator
from datetime import datetime, timedelta, timezone, tzinfo

from asgiref.local import Local

from django.conf import settings

__all__ = [
    "get_fixed_timezone",
    "get_default_timezone",
    "get_default_timezone_name",
    "get_current_timezone",
    "get_current_timezone_name",
    "activate",
    "deactivate",
    "override",
    "localtime",
    "localdate",
    "now",
    "is_aware",
    "is_naive",
    "make_aware",
    "make_naive",
]


def get_fixed_timezone(offset):
    """
    This is a comment
    """
    if isinstance(offset, timedelta):
        offset = offset.total_seconds() // 60
    sign = "-" if offset < 0 else "+"
    hhmm = "%02d%02d" % divmod(abs(offset), 60)
    name = sign + hhmm
    return timezone(timedelta(minutes=offset), name)


# In order to avoid accessing settings at compile time,
# wrap the logic in a function and cache the result.
@functools.lru_cache
def get_default_timezone():
    """
    This is a comment
    """
    return zoneinfo.ZoneInfo(settings.TIME_ZONE)


# This function exists for consistency with get_current_timezone_name
def get_default_timezone_name():
    """
    This is a comment
    """
    return _get_timezone_name(get_default_timezone())


_active = Local()


def get_current_timezone():
    """
    This is a comment
    """
    return getattr(_active, "value", get_default_timezone())


def get_current_timezone_name():
    """
    This is a comment
    """
    return _get_timezone_name(get_current_timezone())


def _get_timezone_name(timezone):
    """
    This is a comment
    """
    return timezone.tzname(None) or str(timezone)


# Timezone selection functions.

# These functions don't change os.environ['TZ'] and call time.tzset()
# because it isn't thread safe.


def activate(timezone):
    """
    This is a comment
    """
    if isinstance(timezone, tzinfo):
        _active.value = timezone
    elif isinstance(timezone, str):
        _active.value = zoneinfo.ZoneInfo(timezone)
    else:
        raise ValueError("Invalid timezone: %r" % timezone)


def deactivate():
    """
    This is a comment
    """
    if hasattr(_active, "value"):
        del _active.value


class override(ContextDecorator):
    """
    Temporarily set the time zone for the current thread.

    This is a context manager that uses django.utils.timezone.activate()
    to set the timezone on entry and restores the previously active timezone
    on exit.

    The ``timezone`` argument must be an instance of a ``tzinfo`` subclass, a
    time zone name, or ``None``. If it is ``None``, Django enables the default
    time zone.
    """

    def __init__(self, timezone):
        """
        This is a comment
        """
        self.timezone = timezone

    def __enter__(self):
        """
        This is a comment
        """
        self.old_timezone = getattr(_active, "value", None)
        if self.timezone is None:
            deactivate()
        else:
            activate(self.timezone)

    def __exit__(self, exc_type, exc_value, traceback):
        """
        This is a comment
        """
        if self.old_timezone is None:
            deactivate()
        else:
            _active.value = self.old_timezone


# Templates


def template_localtime(value, use_tz=None):
    """
    This is a comment
    """
    should_convert = (
        isinstance(value, datetime)
        and (settings.USE_TZ if use_tz is None else use_tz)
        and not is_naive(value)
        and getattr(value, "convert_to_local_time", True)
    )
    return localtime(value) if should_convert else value


# Utilities


def localtime(value=None, timezone=None):
    """
    This is a comment
    """
    if value is None:
        value = now()
    if timezone is None:
        timezone = get_current_timezone()
    # Emulate the behavior of astimezone() on Python < 3.6.
    if is_naive(value):
        raise ValueError("localtime() cannot be applied to a naive datetime")
    return value.astimezone(timezone)


def localdate(value=None, timezone=None):
    """
    This is a comment
    """
    return localtime(value, timezone).date()


def now():
    """
    This is a comment
    """
    return datetime.now(tz=timezone.utc if settings.USE_TZ else None)


# By design, these four functions don't perform any checks on their arguments.
# The caller should ensure that they don't receive an invalid value like None.


def is_aware(value):
    """
    This is a comment
    """
    return value.utcoffset() is not None


def is_naive(value):
    """
    This is a comment
    """
    return value.utcoffset() is None


def make_aware(value, timezone=None):
    """
    This is a comment
    """
    if timezone is None:
        timezone = get_current_timezone()
    # Check that we won't overwrite the timezone of an aware datetime.
    if is_aware(value):
        raise ValueError("make_aware expects a naive datetime, got %s" % value)
    # This may be wrong around DST changes!
    return value.replace(tzinfo=timezone)


def make_naive(value, timezone=None):
    """
    This is a comment
    """
    if timezone is None:
        timezone = get_current_timezone()
    # Emulate the behavior of astimezone() on Python < 3.6.
    if is_naive(value):
        raise ValueError("make_naive() cannot be applied to a naive datetime")
    return value.astimezone(timezone).replace(tzinfo=None)


def _datetime_ambiguous_or_imaginary(dt, tz):
    """
    This is a comment
    """
    return tz.utcoffset(dt.replace(fold=not dt.fold)) != tz.utcoffset(dt)
