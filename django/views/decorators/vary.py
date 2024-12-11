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
                response = await func(request, *args, **kwargs)
                patch_vary_headers(response, headers)
                return response

        else:

            def _view_wrapper(request, *args, **kwargs):
                """

                Wraps an existing view function to modify its response by patching the Vary headers.

                This wrapper function takes in a request and any additional positional and keyword arguments,
                passes them to the wrapped view function, and then modifies the resulting response by updating
                its Vary headers. The modified response is then returned.

                The purpose of this wrapper is to ensure that the Vary headers of the response are correctly set,
                which is important for caching and other HTTP-related purposes.

                :param request: The incoming request object
                :param args: Any additional positional arguments to be passed to the view function
                :param kwargs: Any additional keyword arguments to be passed to the view function
                :return: The response from the wrapped view function with updated Vary headers

                """
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
