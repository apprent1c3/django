from functools import wraps

from asgiref.sync import iscoroutinefunction

from django.utils.cache import patch_vary_headers


def vary_on_headers(*headers):
    """
    A view decorator that modifies the Vary header of the response by adding the specified headers, to indicate that the response varies based on these headers. The header names are case-insensitive.
    """

    def decorator(func):
        """

        Decorator to patch the 'Vary' response headers for a view function.

        Adds the 'Vary' headers to the response of the decorated function, regardless of whether it is an asynchronous or synchronous function.

        :param func: The view function to be decorated
        :returns: The decorated view function with patched 'Vary' response headers

        """
        if iscoroutinefunction(func):

            async def _view_wrapper(request, *args, **kwargs):
                response = await func(request, *args, **kwargs)
                patch_vary_headers(response, headers)
                return response

        else:

            def _view_wrapper(request, *args, **kwargs):
                response = func(request, *args, **kwargs)
                patch_vary_headers(response, headers)
                return response

        return wraps(func)(_view_wrapper)

    return decorator


vary_on_cookie = vary_on_headers("Cookie")
vary_on_cookie.__doc__ = (
    'A view decorator that adds "Cookie" to the Vary header of a response. This '
    "indicates that a page's contents depends on cookies."
)
