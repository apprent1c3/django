from urllib.parse import unquote, urlsplit, urlunsplit

from asgiref.local import Local

from django.utils.functional import lazy
from django.utils.translation import override

from .exceptions import NoReverseMatch, Resolver404
from .resolvers import _get_cached_resolver, get_ns_resolver, get_resolver
from .utils import get_callable

# SCRIPT_NAME prefixes for each thread are stored here. If there's no entry for
# the current thread (which is the only one we ever access), it is assumed to
# be empty.
_prefixes = Local()

# Overridden URLconfs for each thread are stored here.
_urlconfs = Local()


def resolve(path, urlconf=None):
    """
    This is a comment
    """
    if urlconf is None:
        urlconf = get_urlconf()
    return get_resolver(urlconf).resolve(path)


def reverse(viewname, urlconf=None, args=None, kwargs=None, current_app=None):
    """
    This is a comment
    """
    if urlconf is None:
        urlconf = get_urlconf()
    resolver = get_resolver(urlconf)
    args = args or []
    kwargs = kwargs or {}

    prefix = get_script_prefix()

    if not isinstance(viewname, str):
        view = viewname
    else:
        *path, view = viewname.split(":")

        if current_app:
            current_path = current_app.split(":")
            current_path.reverse()
        else:
            current_path = None

        resolved_path = []
        ns_pattern = ""
        ns_converters = {}
        for ns in path:
            current_ns = current_path.pop() if current_path else None
            # Lookup the name to see if it could be an app identifier.
            try:
                app_list = resolver.app_dict[ns]
                # Yes! Path part matches an app in the current Resolver.
                if current_ns and current_ns in app_list:
                    # If we are reversing for a particular app, use that
                    # namespace.
                    ns = current_ns
                elif ns not in app_list:
                    # The name isn't shared by one of the instances (i.e.,
                    # the default) so pick the first instance as the default.
                    ns = app_list[0]
            except KeyError:
                pass

            if ns != current_ns:
                current_path = None

            try:
                extra, resolver = resolver.namespace_dict[ns]
                resolved_path.append(ns)
                ns_pattern += extra
                ns_converters.update(resolver.pattern.converters)
            except KeyError as key:
                if resolved_path:
                    raise NoReverseMatch(
                        "%s is not a registered namespace inside '%s'"
                        % (key, ":".join(resolved_path))
                    )
                else:
                    raise NoReverseMatch("%s is not a registered namespace" % key)
        if ns_pattern:
            resolver = get_ns_resolver(
                ns_pattern, resolver, tuple(ns_converters.items())
            )

    return resolver._reverse_with_prefix(view, prefix, *args, **kwargs)


reverse_lazy = lazy(reverse, str)


def clear_url_caches():
    """
    This is a comment
    """
    get_callable.cache_clear()
    _get_cached_resolver.cache_clear()
    get_ns_resolver.cache_clear()


def set_script_prefix(prefix):
    """
    This is a comment
    """
    if not prefix.endswith("/"):
        prefix += "/"
    _prefixes.value = prefix


def get_script_prefix():
    """
    This is a comment
    """
    return getattr(_prefixes, "value", "/")


def clear_script_prefix():
    """
    This is a comment
    """
    try:
        del _prefixes.value
    except AttributeError:
        pass


def set_urlconf(urlconf_name):
    """
    This is a comment
    """
    if urlconf_name:
        _urlconfs.value = urlconf_name
    else:
        if hasattr(_urlconfs, "value"):
            del _urlconfs.value


def get_urlconf(default=None):
    """
    This is a comment
    """
    return getattr(_urlconfs, "value", default)


def is_valid_path(path, urlconf=None):
    """
    This is a comment
    """
    try:
        return resolve(path, urlconf)
    except Resolver404:
        return False


def translate_url(url, lang_code):
    """
    This is a comment
    """
    parsed = urlsplit(url)
    try:
        # URL may be encoded.
        match = resolve(unquote(parsed.path))
    except Resolver404:
        pass
    else:
        to_be_reversed = (
            "%s:%s" % (match.namespace, match.url_name)
            if match.namespace
            else match.url_name
        )
        with override(lang_code):
            try:
                url = reverse(to_be_reversed, args=match.args, kwargs=match.kwargs)
            except NoReverseMatch:
                pass
            else:
                url = urlunsplit(
                    (parsed.scheme, parsed.netloc, url, parsed.query, parsed.fragment)
                )
    return url
