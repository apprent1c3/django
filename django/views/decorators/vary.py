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
        if iscoroutinefunction(func):

            async def _view_wrapper(request, *args, **kwargs):
                """

                View wrapper function to modify the response of an asynchronous view function.

                This function takes an asynchronous request, calls the wrapped view function with the provided arguments,
                and then patches the headers of the response before returning it. The headers to be patched are specified
                in the 'headers' variable.

                The purpose of this function is to handle the insertion of varying headers into responses in a centralized manner,
                allowing for easier management of cache control and other response headers that may need to vary based on user
                or request context.

                :param request: The incoming request to be passed to the wrapped view function
                :param args: Additional positional arguments to be passed to the wrapped view function
                :param kwargs: Additional keyword arguments to be passed to the wrapped view function
                :return: The response from the wrapped view function with modified headers

                """
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
