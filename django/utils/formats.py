import datetime
import decimal
import functools
import re
import unicodedata
from importlib import import_module

from django.conf import settings
from django.utils import dateformat, numberformat
from django.utils.functional import lazy
from django.utils.translation import check_for_language, get_language, to_locale

# format_cache is a mapping from (format_type, lang) to the format string.
# By using the cache, it is possible to avoid running get_format_modules
# repeatedly.
_format_cache = {}
_format_modules_cache = {}

ISO_INPUT_FORMATS = {
    "DATE_INPUT_FORMATS": ["%Y-%m-%d"],
    "TIME_INPUT_FORMATS": ["%H:%M:%S", "%H:%M:%S.%f", "%H:%M"],
    "DATETIME_INPUT_FORMATS": [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ],
}


FORMAT_SETTINGS = frozenset(
    [
        "DECIMAL_SEPARATOR",
        "THOUSAND_SEPARATOR",
        "NUMBER_GROUPING",
        "FIRST_DAY_OF_WEEK",
        "MONTH_DAY_FORMAT",
        "TIME_FORMAT",
        "DATE_FORMAT",
        "DATETIME_FORMAT",
        "SHORT_DATE_FORMAT",
        "SHORT_DATETIME_FORMAT",
        "YEAR_MONTH_FORMAT",
        "DATE_INPUT_FORMATS",
        "TIME_INPUT_FORMATS",
        "DATETIME_INPUT_FORMATS",
    ]
)


def reset_format_cache():
    """Clear any cached formats.

    This method is provided primarily for testing purposes,
    so that the effects of cached formats can be removed.
    """
    global _format_cache, _format_modules_cache
    _format_cache = {}
    _format_modules_cache = {}


def iter_format_modules(lang, format_module_path=None):
    """

    Find and yield format modules for a given language.

    The function iterates over predefined and custom locations to find format modules
    for the specified language and its base locale, returning them one by one.

    :param lang: The language code to find format modules for
    :param format_module_path: Optional path or list of paths to search for format modules

    """
    if not check_for_language(lang):
        return

    if format_module_path is None:
        format_module_path = settings.FORMAT_MODULE_PATH

    format_locations = []
    if format_module_path:
        if isinstance(format_module_path, str):
            format_module_path = [format_module_path]
        for path in format_module_path:
            format_locations.append(path + ".%s")
    format_locations.append("django.conf.locale.%s")
    locale = to_locale(lang)
    locales = [locale]
    if "_" in locale:
        locales.append(locale.split("_")[0])
    for location in format_locations:
        for loc in locales:
            try:
                yield import_module("%s.formats" % (location % loc))
            except ImportError:
                pass


def get_format_modules(lang=None):
    """
    Return a list of format modules available for a given language, defaulting to the current language if not specified. The result is cached to improve performance for subsequent requests with the same language.
    """
    if lang is None:
        lang = get_language()
    if lang not in _format_modules_cache:
        _format_modules_cache[lang] = list(
            iter_format_modules(lang, settings.FORMAT_MODULE_PATH)
        )
    return _format_modules_cache[lang]


def get_format(format_type, lang=None, use_l10n=None):
    """
    Retrieves the specified format for the current language, allowing for optional localization override. The function returns the format type (e.g. 'DATE_FORMAT') as configured for the current locale, with flexibility to force localization or use a default language.
    """
    if use_l10n is None:
        use_l10n = True
    if use_l10n and lang is None:
        lang = get_language()
    format_type = str(format_type)  # format_type may be lazy.
    cache_key = (format_type, lang)
    try:
        return _format_cache[cache_key]
    except KeyError:
        pass

    # The requested format_type has not been cached yet. Try to find it in any
    # of the format_modules for the given lang if l10n is enabled. If it's not
    # there or if l10n is disabled, fall back to the project settings.
    val = None
    if use_l10n:
        for module in get_format_modules(lang):
            val = getattr(module, format_type, None)
            if val is not None:
                break
    if val is None:
        if format_type not in FORMAT_SETTINGS:
            return format_type
        val = getattr(settings, format_type)
    elif format_type in ISO_INPUT_FORMATS:
        # If a list of input formats from one of the format_modules was
        # retrieved, make sure the ISO_INPUT_FORMATS are in this list.
        val = list(val)
        for iso_input in ISO_INPUT_FORMATS.get(format_type, ()):
            if iso_input not in val:
                val.append(iso_input)
    _format_cache[cache_key] = val
    return val


get_format_lazy = lazy(get_format, str, list, tuple)


def date_format(value, format=None, use_l10n=None):
    """
    Format a datetime.date or datetime.datetime object using a
    localizable format.

    If use_l10n is provided and is not None, that will force the value to
    be localized (or not), otherwise it's always localized.
    """
    return dateformat.format(
        value, get_format(format or "DATE_FORMAT", use_l10n=use_l10n)
    )


def time_format(value, format=None, use_l10n=None):
    """
    Format a datetime.time object using a localizable format.

    If use_l10n is provided and is not None, it forces the value to
    be localized (or not), otherwise it's always localized.
    """
    return dateformat.time_format(
        value, get_format(format or "TIME_FORMAT", use_l10n=use_l10n)
    )


def number_format(value, decimal_pos=None, use_l10n=None, force_grouping=False):
    """
    Format a numeric value using localization settings, allowing control over decimal places, thousand separators, and grouping.
    """
    if use_l10n is None:
        use_l10n = True
    lang = get_language() if use_l10n else None
    return numberformat.format(
        value,
        get_format("DECIMAL_SEPARATOR", lang, use_l10n=use_l10n),
        decimal_pos,
        get_format("NUMBER_GROUPING", lang, use_l10n=use_l10n),
        get_format("THOUSAND_SEPARATOR", lang, use_l10n=use_l10n),
        force_grouping=force_grouping,
        use_l10n=use_l10n,
    )


def localize(value, use_l10n=None):
    """
    Formats the given value as a string according to the current locale, if applicable. Supports localization of dates, numbers, and other data types. The localization can be forced or disabled using the `use_l10n` parameter.
    """
    if isinstance(value, str):  # Handle strings first for performance reasons.
        return value
    elif isinstance(value, bool):  # Make sure booleans don't get treated as numbers
        return str(value)
    elif isinstance(value, (decimal.Decimal, float, int)):
        if use_l10n is False:
            return str(value)
        return number_format(value, use_l10n=use_l10n)
    elif isinstance(value, datetime.datetime):
        return date_format(value, "DATETIME_FORMAT", use_l10n=use_l10n)
    elif isinstance(value, datetime.date):
        return date_format(value, use_l10n=use_l10n)
    elif isinstance(value, datetime.time):
        return time_format(value, use_l10n=use_l10n)
    return value


def localize_input(value, default=None):
    """
    Localize an input value according to the current locale formatting rules.

    Args:
        value: The input value to be localized. Can be a string, boolean, number, date, time, or datetime object.
        default: Optional default format string for date, time and datetime objects.

    Returns:
        The input value formatted according to the current locale settings.
    """
    if isinstance(value, str):  # Handle strings first for performance reasons.
        return value
    elif isinstance(value, bool):  # Don't treat booleans as numbers.
        return str(value)
    elif isinstance(value, (decimal.Decimal, float, int)):
        return number_format(value)
    elif isinstance(value, datetime.datetime):
        format = default or get_format("DATETIME_INPUT_FORMATS")[0]
        format = sanitize_strftime_format(format)
        return value.strftime(format)
    elif isinstance(value, datetime.date):
        format = default or get_format("DATE_INPUT_FORMATS")[0]
        format = sanitize_strftime_format(format)
        return value.strftime(format)
    elif isinstance(value, datetime.time):
        format = default or get_format("TIME_INPUT_FORMATS")[0]
        return value.strftime(format)
    return value


@functools.lru_cache
def sanitize_strftime_format(fmt):
    """
    Ensure that certain specifiers in a strftime format string are correctly padded with leading zeros, fixing issues with glibc on Linux for years less than 1000.
    """
    if datetime.date(1, 1, 1).strftime("%Y") == "0001":
        return fmt
    mapping = {"C": 2, "F": 10, "G": 4, "Y": 4}
    return re.sub(
        r"((?:^|[^%])(?:%%)*)%([CFGY])",
        lambda m: r"%s%%0%s%s" % (m[1], mapping[m[2]], m[2]),
        fmt,
    )


def sanitize_separators(value):
    """
    Sanitizes a numeric value by replacing decimal and thousand separators according to the current locale settings, preparing it for use with form field input.
    """
    if isinstance(value, str):
        parts = []
        decimal_separator = get_format("DECIMAL_SEPARATOR")
        if decimal_separator in value:
            value, decimals = value.split(decimal_separator, 1)
            parts.append(decimals)
        if settings.USE_THOUSAND_SEPARATOR:
            thousand_sep = get_format("THOUSAND_SEPARATOR")
            if (
                thousand_sep == "."
                and value.count(".") == 1
                and len(value.split(".")[-1]) != 3
            ):
                # Special case where we suspect a dot meant decimal separator
                # (see #22171).
                pass
            else:
                for replacement in {
                    thousand_sep,
                    unicodedata.normalize("NFKD", thousand_sep),
                }:
                    value = value.replace(replacement, "")
        parts.append(value)
        value = ".".join(reversed(parts))
    return value
