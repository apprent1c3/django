"""
Decorators for views based on HTTP headers.
"""

import datetime
from functools import wraps

from asgiref.sync import iscoroutinefunction

from django.http import HttpResponseNotAllowed
from django.middleware.http import ConditionalGetMiddleware
from django.utils import timezone
from django.utils.cache import get_conditional_response
from django.utils.decorators import decorator_from_middleware
from django.utils.http import http_date, quote_etag
from django.utils.log import log_response

conditional_page = decorator_from_middleware(ConditionalGetMiddleware)


def require_http_methods(request_method_list):
    """
    Restricts a view to only accept specific HTTP request methods, returning a 405 Method Not Allowed response for unsupported methods. The allowed methods should be specified in uppercase.
    """

    def decorator(func):
        """
        Decorates a view function to restrict the allowed HTTP request methods.

        Checks if the incoming request method is in the allowed list, returning a 405 
        Method Not Allowed response if not, and otherwise calling the view function.

        Supports both synchronous and asynchronous view functions.
        """
        if iscoroutinefunction(func):

            @wraps(func)
            async def inner(request, *args, **kwargs):
                """
                Ensures that an asynchronous function only responds to allowed HTTP request methods. If the request method is not in the approved list, it returns a 'Method Not Allowed' response. Otherwise, it proceeds to call the wrapped function.
                """
                if request.method not in request_method_list:
                    response = HttpResponseNotAllowed(request_method_list)
                    log_response(
                        "Method Not Allowed (%s): %s",
                        request.method,
                        request.path,
                        response=response,
                        request=request,
                    )
                    return response
                return await func(request, *args, **kwargs)

        else:

            @wraps(func)
            def inner(request, *args, **kwargs):
                """

                Checks if the HTTP request method is allowed and calls the wrapped function if it is.

                If the request method is not in the list of allowed methods, it returns a 405 Method Not Allowed response.

                :param request: The current HTTP request
                :param args: Variable number of positional arguments
                :param kwargs: Variable number of keyword arguments
                :return: The response from the wrapped function or a 405 Method Not Allowed response

                """
                if request.method not in request_method_list:
                    response = HttpResponseNotAllowed(request_method_list)
                    log_response(
                        "Method Not Allowed (%s): %s",
                        request.method,
                        request.path,
                        response=response,
                        request=request,
                    )
                    return response
                return func(request, *args, **kwargs)

        return inner

    return decorator


require_GET = require_http_methods(["GET"])
require_GET.__doc__ = "Decorator to require that a view only accepts the GET method."

require_POST = require_http_methods(["POST"])
require_POST.__doc__ = "Decorator to require that a view only accepts the POST method."

require_safe = require_http_methods(["GET", "HEAD"])
require_safe.__doc__ = (
    "Decorator to require that a view only accepts safe methods: GET and HEAD."
)


def condition(etag_func=None, last_modified_func=None):
    """
    This decorator enables conditional retrieval or modification of a resource by adding support for ETag and Last-Modified headers in HTTP requests. 
    It accepts two callables, one to compute the ETag and the other to calculate the last modified time of the resource, both taking the same parameters as the view function they decorate. 
    The decorator will return an HTTP 304 response if the resource is unmodified, a 412 response if a precondition fails, or the decorated view's response with the added ETag and Last-Modified headers if the request method is safe.
    """

    def decorator(func):
        """
        A decorator that enables conditional responses based on ETag and Last-Modified headers.

        It pre-processes incoming requests to determine if a conditional response can be returned,
        and post-processes outgoing responses to set ETag and Last-Modified headers as necessary.

        The decorator can handle both synchronous and asynchronous functions, and is adaptable to
        different use cases through the use of customizable etag and last modified functions.
        """
        def _pre_process_request(request, *args, **kwargs):
            # Compute values (if any) for the requested resource.
            """
            Pre-processes a request, computing last modified timestamp and ETAG values, 
            and returning a conditional response based on these values along with the 
            computed ETAG and last modified timestamp.
            """
            res_last_modified = None
            if last_modified_func:
                if dt := last_modified_func(request, *args, **kwargs):
                    if not timezone.is_aware(dt):
                        dt = timezone.make_aware(dt, datetime.timezone.utc)
                    res_last_modified = int(dt.timestamp())
            # The value from etag_func() could be quoted or unquoted.
            res_etag = etag_func(request, *args, **kwargs) if etag_func else None
            res_etag = quote_etag(res_etag) if res_etag is not None else None
            response = get_conditional_response(
                request,
                etag=res_etag,
                last_modified=res_last_modified,
            )
            return response, res_etag, res_last_modified

        def _post_process_request(request, response, res_etag, res_last_modified):
            # Set relevant headers on the response if they don't already exist
            # and if the request method is safe.
            """
            Adds HTTP headers for Last-Modified and ETag to the response object if they are not already present, for GET and HEAD requests.
            """
            if request.method in ("GET", "HEAD"):
                if res_last_modified and not response.has_header("Last-Modified"):
                    response.headers["Last-Modified"] = http_date(res_last_modified)
                if res_etag:
                    response.headers.setdefault("ETag", res_etag)

        if iscoroutinefunction(func):

            @wraps(func)
            async def inner(request, *args, **kwargs):
                """
                Wraps an asynchronous function to perform pre- and post-processing of HTTP requests, 
                handling caching and conditional requests based on ETag and Last-Modified headers.
                """
                response, res_etag, res_last_modified = _pre_process_request(
                    request, *args, **kwargs
                )
                if response is None:
                    response = await func(request, *args, **kwargs)
                _post_process_request(request, response, res_etag, res_last_modified)
                return response

        else:

            @wraps(func)
            def inner(request, *args, **kwargs):
                """
                Wraps a function to add pre-processing and post-processing steps to an incoming request.

                Provides a way to execute additional logic before and after the original function call, allowing for
                conditional early returns based on the pre-processing results and modifying the response as needed.

                This wrapper ensures that the original function's behavior remains unchanged, while enabling the injection
                of custom request handling logic at key points during the request processing pipeline.
                """
                response, res_etag, res_last_modified = _pre_process_request(
                    request, *args, **kwargs
                )
                if response is None:
                    response = func(request, *args, **kwargs)
                _post_process_request(request, response, res_etag, res_last_modified)
                return response

        return inner

    return decorator


# Shortcut decorators for common cases based on ETag or Last-Modified only
def etag(etag_func):
    return condition(etag_func=etag_func)


def last_modified(last_modified_func):
    return condition(last_modified_func=last_modified_func)
