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
    Applies one or more function decorators to a given method, allowing for flexible and dynamic decoration of existing functions.
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
    Convert a function decorator into a method decorator, allowing it to be applied to a specific method of a class. The decorated method is replaced with the decorated version, modifying the class in-place.
    """

    # 'obj' can be a class or a function. If 'obj' is a function at the time it
    # is passed to _dec,  it will eventually be a method of the class it is
    # defined on. If 'obj' is a class, the 'name' is required to be the name
    # of the method that will be decorated.
    def _dec(obj):
        """
        Decorates a class or a specific method within a class by applying the specified decorator.

        :raises ValueError: If the specified method name is not found in the class.
        :raises TypeError: If the attribute to be decorated is not a callable method.
        :returns: The decorated class or the result of the multi-decorate function if a non-class object is provided.
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
    Creates a decorator that integrates the given middleware class with a view function.

    This function returns another function that acts as a decorator. When applied to a view function, 
    it wraps the view with an instance of the middleware class, allowing the middleware to process 
    requests, views, exceptions, and responses. The middleware instance is created with the provided 
    arguments and keyword arguments.

    This decorator supports both synchronous and asynchronous view functions, as well as middleware 
    methods for processing requests, views, exceptions, and responses, making it a versatile tool for 
    building robust and modular web applications. 

    :param middleware_class: The class of the middleware to integrate with the view function.
    :returns: A decorator function that integrates the middleware with a view function.
    """
    def _make_decorator(*m_args, **m_kwargs):
        """
        This function creates a decorator that wraps view functions with middleware functionality.
        The middleware is initialized with the provided arguments and keyword arguments.
        It supports various middleware methods such as process_request, process_view, process_exception, process_template_response, and process_response.
        The decorator handles both synchronous and asynchronous view functions.
        """
        def _decorator(view_func):
            """
            Decorator that wraps a view function with middleware functionality.

            This decorator applies a middleware class to a view function, allowing for custom request and response processing.
            It supports both synchronous and asynchronous view functions.

            The middleware is instantiated with the provided arguments and keyword arguments (`m_args` and `m_kwargs`).
            It then checks for and calls the following middleware methods, if they exist:
            - `process_request`: to modify or return a response before the view is called
            - `process_view`: to modify or return a response before the view is called, with access to the view function and its arguments
            - `process_exception`: to handle exceptions raised by the view
            - `process_template_response`: to modify the response after template rendering
            - `process_response`: to modify the final response

            The decorated view function will behave as if the middleware methods were integrated directly into the view function itself. 
            """
            middleware = middleware_class(view_func, *m_args, **m_kwargs)

            def _pre_process_request(request, *args, **kwargs):
                """

                Pre-processes a request by executing middleware hooks for 'process_request' and 'process_view' if available.

                :return: The result of the middleware hook if it returns a value, otherwise None.

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
                Delegates the handling of an exception to a middleware's exception processing if available, otherwise re-raises the exception.
                """
                if hasattr(middleware, "process_exception"):
                    result = middleware.process_exception(request, exception)
                    if result is not None:
                        return result
                raise

            def _post_process_request(request, response):
                """

                Post-process a request and its corresponding response.

                This function triggers additional processing on a response, such as rendering templates and applying callbacks, 
                allowing middleware to modify the response before it is sent back to the client.

                :param request: The request object associated with the response.
                :param response: The response object to be processed.

                :return: The processed response.

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
                    Wrapper function to handle the lifecycle of a view function, including pre-processing, 
                    exception handling, and post-processing of the request and response.
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
                    Wraps a view function to provide request preprocessing, exception handling, and post-processing functionality. 

                    It first attempts to preprocess the request, handling any premature results. 
                    If preprocessing does not yield a result, it then invokes the underlying view function, 
                    catching any exceptions that may occur and allowing them to be handled. 
                    Finally, it post-processes the request and any generated response before returning the final result.
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
