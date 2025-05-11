"""Functions for use in URLsconfs."""

from functools import partial
from importlib import import_module

from django.core.exceptions import ImproperlyConfigured

from .resolvers import (
    LocalePrefixPattern,
    RegexPattern,
    RoutePattern,
    URLPattern,
    URLResolver,
)


def include(arg, namespace=None):
    """
    Includes a URL configuration module into the main URL configuration.

    Allows for the inclusion of URL patterns from other modules, optionally under a specified namespace or with a given app name.

    Parameters
    ----------
    arg : tuple or str
        Either a URL configuration module (as a string or module object), or a 2-tuple containing the URL configuration module and an app name.
    namespace : str, optional
        Specifies the namespace for the included URL patterns.

    Returns
    -------
    tuple
        A 3-tuple containing the included URL configuration module, the app name, and the namespace.

    Raises
    ------
    ImproperlyConfigured
        If the provided arguments are invalid or inconsistent.

    """
    app_name = None
    if isinstance(arg, tuple):
        # Callable returning a namespace hint.
        try:
            urlconf_module, app_name = arg
        except ValueError:
            if namespace:
                raise ImproperlyConfigured(
                    "Cannot override the namespace for a dynamic module that "
                    "provides a namespace."
                )
            raise ImproperlyConfigured(
                "Passing a %d-tuple to include() is not supported. Pass a "
                "2-tuple containing the list of patterns and app_name, and "
                "provide the namespace argument to include() instead." % len(arg)
            )
    else:
        # No namespace hint - use manually provided namespace.
        urlconf_module = arg

    if isinstance(urlconf_module, str):
        urlconf_module = import_module(urlconf_module)
    patterns = getattr(urlconf_module, "urlpatterns", urlconf_module)
    app_name = getattr(urlconf_module, "app_name", app_name)
    if namespace and not app_name:
        raise ImproperlyConfigured(
            "Specifying a namespace in include() without providing an app_name "
            "is not supported. Set the app_name attribute in the included "
            "module, or pass a 2-tuple containing the list of patterns and "
            "app_name instead.",
        )
    namespace = namespace or app_name
    # Make sure the patterns can be iterated through (without this, some
    # testcases will break).
    if isinstance(patterns, (list, tuple)):
        for url_pattern in patterns:
            pattern = getattr(url_pattern, "pattern", None)
            if isinstance(pattern, LocalePrefixPattern):
                raise ImproperlyConfigured(
                    "Using i18n_patterns in an included URLconf is not allowed."
                )
    return (urlconf_module, app_name, namespace)


def _path(route, view, kwargs=None, name=None, Pattern=None):
    """
    Returns a URL pattern or resolver based on the provided route and view.

    :param route: The URL route pattern
    :param view: The view function or a list/tuple for URL includes
    :param kwargs: Additional keyword arguments for the URL pattern
    :param name: The name of the URL pattern
    :param Pattern: The pattern class to use for the URL

    :raises TypeError: If the provided kwargs is not a dict or if the view is not a callable or a valid include.

    :returns: A URL pattern or resolver instance
    """
    from django.views import View

    if kwargs is not None and not isinstance(kwargs, dict):
        raise TypeError(
            f"kwargs argument must be a dict, but got {kwargs.__class__.__name__}."
        )
    if isinstance(view, (list, tuple)):
        # For include(...) processing.
        pattern = Pattern(route, is_endpoint=False)
        urlconf_module, app_name, namespace = view
        return URLResolver(
            pattern,
            urlconf_module,
            kwargs,
            app_name=app_name,
            namespace=namespace,
        )
    elif callable(view):
        pattern = Pattern(route, name=name, is_endpoint=True)
        return URLPattern(pattern, view, kwargs, name)
    elif isinstance(view, View):
        view_cls_name = view.__class__.__name__
        raise TypeError(
            f"view must be a callable, pass {view_cls_name}.as_view(), not "
            f"{view_cls_name}()."
        )
    else:
        raise TypeError(
            "view must be a callable or a list/tuple in the case of include()."
        )


path = partial(_path, Pattern=RoutePattern)
re_path = partial(_path, Pattern=RegexPattern)
