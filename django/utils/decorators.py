"Functions that help with dynamically creating decorators for views."

from functools import partial, update_wrapper, wraps

from asgiref.sync import iscoroutinefunction


class classonlymethod(classmethod):
    def __get__(self, instance, cls=None):
        if instance is not None:
            raise AttributeError(
                "This method is available only on the class, not on instances."
            )
        return super().__get__(instance, cls)


def _update_method_wrapper(_wrapper, decorator):
    # _multi_decorate()'s bound_method isn't available in this scope. Cheat by
    # using it on a dummy function.
    @decorator
    def dummy(*args, **kwargs):
        pass

    update_wrapper(_wrapper, dummy)


def _multi_decorate(decorators, method):
    """
    Decorate `method` with one or more function decorators. `decorators` can be
    a single decorator or an iterable of decorators.
    """
    if hasattr(decorators, "__iter__"):
        # Apply a list/tuple of decorators if 'decorators' is one. Decorator
        # functions are applied so that the call order is the same as the
        # order in which they appear in the iterable.
        decorators = decorators[::-1]
    else:
        decorators = [decorators]

    def _wrapper(self, *args, **kwargs):
        # bound_method has the signature that 'decorator' expects i.e. no
        # 'self' argument, but it's a closure over self so it can call
        # 'func'. Also, wrap method.__get__() in a function because new
        # attributes can't be set on bound method objects, only on functions.
        bound_method = wraps(method)(partial(method.__get__(self, type(self))))
        for dec in decorators:
            bound_method = dec(bound_method)
        return bound_method(*args, **kwargs)

    # Copy any attributes that a decorator adds to the function it decorates.
    for dec in decorators:
        _update_method_wrapper(_wrapper, dec)
    # Preserve any existing attributes of 'method', including the name.
    update_wrapper(_wrapper, method)
    return _wrapper


def method_decorator(decorator, name=""):
    """
    Convert a function decorator into a method decorator
    """

    # 'obj' can be a class or a function. If 'obj' is a function at the time it
    # is passed to _dec,  it will eventually be a method of the class it is
    # defined on. If 'obj' is a class, the 'name' is required to be the name
    # of the method that will be decorated.
    def _dec(obj):
        """
        Decorates a class method with a given decorator.

        The function takes an object and decorates a specified method within that object.
        It checks if the provided object is a class and if the specified method exists and is callable.
        If the object is not a class, it applies the decorator to the object directly.

        Raised Exceptions:
            ValueError: If the `name` parameter does not match a method of the decorated class.
            TypeError: If the attribute specified by `name` is not callable.

        Returns:
            The decorated class or object.

        """
        if not isinstance(obj, type):
            return _multi_decorate(decorator, obj)
        if not (name and hasattr(obj, name)):
            raise ValueError(
                "The keyword argument `name` must be the name of a method "
                "of the decorated class: %s. Got '%s' instead." % (obj, name)
            )
        method = getattr(obj, name)
        if not callable(method):
            raise TypeError(
                "Cannot decorate '%s' as it isn't a callable attribute of "
                "%s (%s)." % (name, obj, method)
            )
        _wrapper = _multi_decorate(decorator, method)
        setattr(obj, name, _wrapper)
        return obj

    # Don't worry about making _dec look similar to a list/tuple as it's rather
    # meaningless.
    if not hasattr(decorator, "__iter__"):
        update_wrapper(_dec, decorator)
    # Change the name to aid debugging.
    obj = decorator if hasattr(decorator, "__name__") else decorator.__class__
    _dec.__name__ = "method_decorator(%s)" % obj.__name__
    return _dec


def decorator_from_middleware_with_args(middleware_class):
    """
    Like decorator_from_middleware, but return a function
    that accepts the arguments to be passed to the middleware_class.
    Use like::

         cache_page = decorator_from_middleware_with_args(CacheMiddleware)
         # ...

         @cache_page(3600)
         def my_view(request):
             # ...
    """
    return make_middleware_decorator(middleware_class)


def decorator_from_middleware(middleware_class):
    """
    Given a middleware class (not an instance), return a view decorator. This
    lets you use middleware functionality on a per-view basis. The middleware
    is created with no params passed.
    """
    return make_middleware_decorator(middleware_class)()


def make_middleware_decorator(middleware_class):
    """
    Creates a decorator that applies the provided middleware class to a view function.

    This decorator enables the middleware to interact with the view function at multiple stages, including:
    - Pre-processing the request
    - Handling exceptions
    - Post-processing the response

    It supports both synchronous and asynchronous view functions, and provides a flexible way to inject middleware logic into the request-response cycle.

    The middleware class is expected to provide methods for these stages, which will be called if they exist:
    - `process_request`: allowing the middleware to inspect or modify the request
    - `process_view`: allowing the middleware to inspect or modify the request and view function
    - `process_exception`: allowing the middleware to handle exceptions raised by the view function
    - `process_template_response`: allowing the middleware to inspect or modify the template response
    - `process_response`: allowing the middleware to inspect or modify the final response

    :arg middleware_class: The middleware class to apply to the view function
    :returns: A decorator that applies the middleware to a view function
    """
    def _make_decorator(*m_args, **m_kwargs):
        """
        Creates a decorator that applies middleware to a view function.

        The middleware is instantiated with the provided arguments and is expected to have
        methods for processing requests, views, and responses. These methods are called at
        the corresponding stages of the request-response cycle, allowing the middleware to
        modify the flow of the application.

        The created decorator supports both synchronous and asynchronous view functions.

        """
        def _decorator(view_func):
            """
            A decorator that wraps a view function with middleware functionality.

            This decorator creates a wrapper function that applies the middleware to the view function,
            allowing for pre-processing of requests, processing of exceptions, and post-processing of responses.

            The middleware is applied based on the presence of specific methods, including process_request,
            process_view, process_exception, process_template_response, and process_response.

            The wrapper function handles both synchronous and asynchronous view functions, and ensures that
            the original view function's signature and behavior are preserved.

            The purpose of this decorator is to provide a flexible and reusable way to apply middleware to
            view functions, allowing for a variety of use cases such as authentication, caching, and logging.

            """
            middleware = middleware_class(view_func, *m_args, **m_kwargs)

            def _pre_process_request(request, *args, **kwargs):
                """
                Pre-processes a request by invoking middleware hooks if available.

                Checks for and executes middleware's :meth:`process_request` and 
                :meth:`process_view` methods, returning their result if not None.
                """
                if hasattr(middleware, "process_request"):
                    result = middleware.process_request(request)
                    if result is not None:
                        return result
                if hasattr(middleware, "process_view"):
                    result = middleware.process_view(request, view_func, args, kwargs)
                    if result is not None:
                        return result
                return None

            def _process_exception(request, exception):
                """
                .. function:: _process_exception(request, exception)
                   :return: Exception handling result or raises the exception if not handled

                   Handles an exception that occurred during request processing by delegating to the middleware's exception handling logic, if available.
                """
                if hasattr(middleware, "process_exception"):
                    result = middleware.process_exception(request, exception)
                    if result is not None:
                        return result
                raise

            def _post_process_request(request, response):
                """
                Post-processes an HTTP request and its corresponding response.

                Performs additional processing on the response by invoking middleware methods
                if available. The processing may include rendering templates and applying
                post-render callbacks, or directly processing the response.

                Args:
                    request: The HTTP request object.
                    response: The HTTP response object.

                Returns:
                    The post-processed HTTP response object.
                """
                if hasattr(response, "render") and callable(response.render):
                    if hasattr(middleware, "process_template_response"):
                        response = middleware.process_template_response(
                            request, response
                        )
                    # Defer running of process_response until after the template
                    # has been rendered:
                    if hasattr(middleware, "process_response"):

                        def callback(response):
                            return middleware.process_response(request, response)

                        response.add_post_render_callback(callback)
                else:
                    if hasattr(middleware, "process_response"):
                        return middleware.process_response(request, response)
                return response

            if iscoroutinefunction(view_func):

                async def _view_wrapper(request, *args, **kwargs):
                    """
                    Wraps a view function to perform common request processing tasks.

                     Handles pre-processing, exception handling, and post-processing for the view function.

                     :param request: The incoming request object
                     :param args: Variable arguments passed to the view function
                     :param kwargs: Keyword arguments passed to the view function
                     :return: The response object after request processing
                    """
                    result = _pre_process_request(request, *args, **kwargs)
                    if result is not None:
                        return result

                    try:
                        response = await view_func(request, *args, **kwargs)
                    except Exception as e:
                        result = _process_exception(request, e)
                        if result is not None:
                            return result

                    return _post_process_request(request, response)

            else:

                def _view_wrapper(request, *args, **kwargs):
                    """
                    Wraps a view function with pre and post processing, as well as exception handling.

                    Handles the lifecycle of a view function call, including initial request preprocessing,
                    exception handling, and final response postprocessing, to provide a standardized and
                    robust interface for view function execution.
                    """
                    result = _pre_process_request(request, *args, **kwargs)
                    if result is not None:
                        return result

                    try:
                        response = view_func(request, *args, **kwargs)
                    except Exception as e:
                        result = _process_exception(request, e)
                        if result is not None:
                            return result

                    return _post_process_request(request, response)

            return wraps(view_func)(_view_wrapper)

        return _decorator

    return _make_decorator


def sync_and_async_middleware(func):
    """
    Mark a middleware factory as returning a hybrid middleware supporting both
    types of request.
    """
    func.sync_capable = True
    func.async_capable = True
    return func


def sync_only_middleware(func):
    """
    Mark a middleware factory as returning a sync middleware.
    This is the default.
    """
    func.sync_capable = True
    func.async_capable = False
    return func


def async_only_middleware(func):
    """Mark a middleware factory as returning an async middleware."""
    func.sync_capable = False
    func.async_capable = True
    return func
