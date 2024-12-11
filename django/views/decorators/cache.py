from functools import wraps

from asgiref.sync import iscoroutinefunction

from django.middleware.cache import CacheMiddleware
from django.utils.cache import add_never_cache_headers, patch_cache_control
from django.utils.decorators import decorator_from_middleware_with_args


def cache_page(timeout, *, cache=None, key_prefix=None):
    """
    Decorator for views that tries getting the page from the cache and
    populates the cache if the page isn't in the cache yet.

    The cache is keyed by the URL and some data from the headers.
    Additionally there is the key prefix that is used to distinguish different
    cache areas in a multi-site setup. You could use the
    get_current_site().domain, for example, as that is unique across a Django
    project.

    Additionally, all headers from the response's Vary header will be taken
    into account on caching -- just like the middleware does.
    """
    return decorator_from_middleware_with_args(CacheMiddleware)(
        page_timeout=timeout,
        cache_alias=cache,
        key_prefix=key_prefix,
    )


def _check_request(request, decorator_name):
    # Ensure argument looks like a request.
    """
    Verify that the provided request object is an instance of HttpRequest.

    This function checks if the given request has a 'META' attribute, which is a characteristic of Django's HttpRequest objects.
    If the request is not an HttpRequest, a TypeError is raised.
    This check is particularly useful when using decorators to ensure they are applied correctly to view functions or methods.
    In the case of decorating class methods, this function will help detect incorrect usage and suggest the use of @method_decorator instead.
    """
    if not hasattr(request, "META"):
        raise TypeError(
            f"{decorator_name} didn't receive an HttpRequest. If you are "
            "decorating a classmethod, be sure to use @method_decorator."
        )


def cache_control(**kwargs):
    def _cache_controller(viewfunc):
        if iscoroutinefunction(viewfunc):

            async def _view_wrapper(request, *args, **kw):
                """
                View wrapper function that prepares and handles the response from a view function.

                This function checks the request for the presence of 'cache_control', then calls the view function
                with the provided arguments and keyword arguments, and finally modifies the response by patching
                its cache control headers before returning the response.

                It is intended for internal use and wraps the original view function with additional
                request checking and response modification functionality.

                :param request: The incoming request object.
                :param args: Variable length non-keyword arguments to be passed to the view function.
                :param kw: Variable length keyword arguments to be passed to the view function.
                :returns: The response object from the view function with modified cache control headers.
                """
                _check_request(request, "cache_control")
                response = await viewfunc(request, *args, **kw)
                patch_cache_control(response, **kwargs)
                return response

        else:

            def _view_wrapper(request, *args, **kw):
                _check_request(request, "cache_control")
                response = viewfunc(request, *args, **kw)
                patch_cache_control(response, **kwargs)
                return response

        return wraps(viewfunc)(_view_wrapper)

    return _cache_controller


def never_cache(view_func):
    """
    Decorator that adds headers to a response so that it will never be cached.
    """

    if iscoroutinefunction(view_func):

        async def _view_wrapper(request, *args, **kwargs):
            _check_request(request, "never_cache")
            response = await view_func(request, *args, **kwargs)
            add_never_cache_headers(response)
            return response

    else:

        def _view_wrapper(request, *args, **kwargs):
            _check_request(request, "never_cache")
            response = view_func(request, *args, **kwargs)
            add_never_cache_headers(response)
            return response

    return wraps(view_func)(_view_wrapper)
