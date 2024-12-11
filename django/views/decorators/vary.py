from functools import wraps

from asgiref.sync import iscoroutinefunction

from django.utils.cache import patch_vary_headers


def vary_on_headers(*headers):
    """
    A view decorator that adds the specified headers to the Vary header of the
    response. Usage:

       @vary_on_headers('Cookie', 'Accept-language')
       def index(request):
           ...

    Note that the header names are not case-sensitive.
    """

    def decorator(func):
        """
        A decorator that patches the 'Vary' headers of the response from the decorated view function.

        It checks if the decorated function is a coroutine and applies the decorator accordingly.
        If the function is a coroutine, it awaits the function's response and then patches the 'Vary' headers.
        If the function is not a coroutine, it directly calls the function and then patches the 'Vary' headers.

        The patched headers are added based on the provided headers, allowing for customization of the 'Vary' headers for the view function's response.

        This decorator is intended to be used with view functions to handle varying headers, such as when the response changes based on different request parameters (e.g., Accept-Language, Accept-Encoding).

        Args:
            func: The view function to be decorated.

        Returns:
            A wrapped version of the input function with patched 'Vary' headers in its response.

        Note:
            The headers to be patched are not defined within this decorator, but are expected to be defined beforehand. The function iscoroutinefunction is used to determine if the input function is a coroutine, and wraps is used to preserve the original function's metadata.
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
