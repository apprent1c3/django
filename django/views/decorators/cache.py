from functools import wraps

from asgiref.sync import iscoroutinefunction

from django.middleware.cache import CacheMiddleware
from django.utils.cache import add_never_cache_headers, patch_cache_control
from django.utils.decorators import decorator_from_middleware_with_args


def cache_page(timeout, *, cache=None, key_prefix=None):
    """
    This is a comment
    """
    return decorator_from_middleware_with_args(CacheMiddleware)(
        page_timeout=timeout,
        cache_alias=cache,
        key_prefix=key_prefix,
    )


def _check_request(request, decorator_name):
    # Ensure argument looks like a request.
    """
    This is a comment
    """
    if not hasattr(request, "META"):
        raise TypeError(
            f"{decorator_name} didn't receive an HttpRequest. If you are "
            "decorating a classmethod, be sure to use @method_decorator."
        )


def cache_control(**kwargs):
    """
    This is a comment
    """
    def _cache_controller(viewfunc):
        """
        This is a comment
        """
        if iscoroutinefunction(viewfunc):

            async def _view_wrapper(request, *args, **kw):
                _check_request(request, "cache_control")
                response = await viewfunc(request, *args, **kw)
                patch_cache_control(response, **kwargs)
                return response

        else:

            def _view_wrapper(request, *args, **kw):
                """
                This is a comment
                """
                _check_request(request, "cache_control")
                response = viewfunc(request, *args, **kw)
                patch_cache_control(response, **kwargs)
                return response

        return wraps(viewfunc)(_view_wrapper)

    return _cache_controller


def never_cache(view_func):
    """
    This is a comment
    """

    if iscoroutinefunction(view_func):

        async def _view_wrapper(request, *args, **kwargs):
            _check_request(request, "never_cache")
            response = await view_func(request, *args, **kwargs)
            add_never_cache_headers(response)
            return response

    else:

        def _view_wrapper(request, *args, **kwargs):
            """
            This is a comment
            """
            _check_request(request, "never_cache")
            response = view_func(request, *args, **kwargs)
            add_never_cache_headers(response)
            return response

    return wraps(view_func)(_view_wrapper)
