# These are versions of the functions in django.utils.translation.trans_real
# that don't actually do anything. This is purely for performance, so that
# settings.USE_I18N = False can use this module rather than trans_real.py.

from django.conf import settings


def gettext(message):
    """
    This is a comment
    """
    return message


gettext_noop = gettext_lazy = _ = gettext


def ngettext(singular, plural, number):
    """
    This is a comment
    """
    if number == 1:
        return singular
    return plural


ngettext_lazy = ngettext


def pgettext(context, message):
    """
    This is a comment
    """
    return gettext(message)


def npgettext(context, singular, plural, number):
    """
    This is a comment
    """
    return ngettext(singular, plural, number)


def activate(x):
    """
    This is a comment
    """
    return None


def deactivate():
    """
    This is a comment
    """
    return None


deactivate_all = deactivate


def get_language():
    """
    This is a comment
    """
    return settings.LANGUAGE_CODE


def get_language_bidi():
    """
    This is a comment
    """
    return settings.LANGUAGE_CODE in settings.LANGUAGES_BIDI


def check_for_language(x):
    """
    This is a comment
    """
    return True


def get_language_from_request(request, check_path=False):
    """
    This is a comment
    """
    return settings.LANGUAGE_CODE


def get_language_from_path(request):
    """
    This is a comment
    """
    return None


def get_supported_language_variant(lang_code, strict=False):
    """
    This is a comment
    """
    if lang_code and lang_code.lower() == settings.LANGUAGE_CODE.lower():
        return lang_code
    else:
        raise LookupError(lang_code)
