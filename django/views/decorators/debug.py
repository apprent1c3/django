import inspect
from functools import wraps

from asgiref.sync import iscoroutinefunction

from django.http import HttpRequest

coroutine_functions_to_sensitive_variables = {}


def sensitive_variables(*variables):
    """
    Indicate which variables used in the decorated function are sensitive so
    that those variables can later be treated in a special way, for example
    by hiding them when logging unhandled exceptions.

    Accept two forms:

    * with specified variable names:

        @sensitive_variables('user', 'password', 'credit_card')
        def my_function(user):
            password = user.pass_word
            credit_card = user.credit_card_number
            ...

    * without any specified variable names, in which case consider all
      variables are sensitive:

        @sensitive_variables()
        def my_function()
            ...
    """
    if len(variables) == 1 and callable(variables[0]):
        raise TypeError(
            "sensitive_variables() must be called to use it as a decorator, "
            "e.g., use @sensitive_variables(), not @sensitive_variables."
        )

    def decorator(func):
        """
        Decorator to mark sensitive variables in a function.

        This decorator allows specifying which variables in a function are sensitive,
        such as those containing personally identifiable information or secrets.
        It supports both synchronous and asynchronous functions.

        :param func: The function to be decorated
        :returns: The decorated function
        """
        if iscoroutinefunction(func):
            sensitive_variables_wrapper = func

            wrapped_func = func
            while getattr(wrapped_func, "__wrapped__", None) is not None:
                wrapped_func = wrapped_func.__wrapped__

            try:
                file_path = inspect.getfile(wrapped_func)
            except TypeError:  # Raises for builtins or native functions.
                raise ValueError(
                    f"{func.__name__} cannot safely be wrapped by "
                    "@sensitive_variables, make it either non-async or defined in a "
                    "Python file (not a builtin or from a native extension)."
                )
            else:
                # A source file may not be available (e.g. in .pyc-only builds),
                # use the first line number instead.
                first_line_number = wrapped_func.__code__.co_firstlineno
                key = hash(f"{file_path}:{first_line_number}")

            if variables:
                coroutine_functions_to_sensitive_variables[key] = variables
            else:
                coroutine_functions_to_sensitive_variables[key] = "__ALL__"

        else:

            @wraps(func)
            def sensitive_variables_wrapper(*func_args, **func_kwargs):
                """
                Wrapper function to annotate sensitive variables and track them during function execution.

                The wrapped function is executed with the provided arguments, and sensitive variables
                are marked as such for later logging or auditing purposes. If no sensitive variables
                are explicitly provided, all variables are considered sensitive by default.
                """
                if variables:
                    sensitive_variables_wrapper.sensitive_variables = variables
                else:
                    sensitive_variables_wrapper.sensitive_variables = "__ALL__"
                return func(*func_args, **func_kwargs)

        return sensitive_variables_wrapper

    return decorator


def sensitive_post_parameters(*parameters):
    """
    Indicate which POST parameters used in the decorated view are sensitive,
    so that those parameters can later be treated in a special way, for example
    by hiding them when logging unhandled exceptions.

    Accept two forms:

    * with specified parameters:

        @sensitive_post_parameters('password', 'credit_card')
        def my_view(request):
            pw = request.POST['password']
            cc = request.POST['credit_card']
            ...

    * without any specified parameters, in which case consider all
      variables are sensitive:

        @sensitive_post_parameters()
        def my_view(request)
            ...
    """
    if len(parameters) == 1 and callable(parameters[0]):
        raise TypeError(
            "sensitive_post_parameters() must be called to use it as a "
            "decorator, e.g., use @sensitive_post_parameters(), not "
            "@sensitive_post_parameters."
        )

    def decorator(view):
        """
        A decorator that marks a view's POST parameters as sensitive, preventing them from being logged.

         The decorator checks if the view is a coroutine function or not and wraps it accordingly.
         It ensures the view receives an HttpRequest object, raising a TypeError if not.
         The `parameters` variable determines which POST parameters are marked as sensitive.
         If `parameters` is not set, all POST parameters are considered sensitive.

         :param view: The view function to be decorated
        """
        if iscoroutinefunction(view):

            @wraps(view)
            async def sensitive_post_parameters_wrapper(request, *args, **kwargs):
                """
                Enables selective logging of POST parameters by marking them as sensitive.

                Parameters can be specified explicitly or, if not provided, all POST parameters are considered sensitive.

                This wrapper ensures that sensitive information is properly handled when interacting with the view.
                """
                if not isinstance(request, HttpRequest):
                    raise TypeError(
                        "sensitive_post_parameters didn't receive an HttpRequest "
                        "object. If you are decorating a classmethod, make sure to use "
                        "@method_decorator."
                    )
                if parameters:
                    request.sensitive_post_parameters = parameters
                else:
                    request.sensitive_post_parameters = "__ALL__"
                return await view(request, *args, **kwargs)

        else:

            @wraps(view)
            def sensitive_post_parameters_wrapper(request, *args, **kwargs):
                """

                Wrapper function to handle sensitive post parameters in HTTP requests.

                Sets the sensitive post parameters attribute on the request object, either to a specified list of parameters or to '__ALL__' if none are provided.

                """
                if not isinstance(request, HttpRequest):
                    raise TypeError(
                        "sensitive_post_parameters didn't receive an HttpRequest "
                        "object. If you are decorating a classmethod, make sure to use "
                        "@method_decorator."
                    )
                if parameters:
                    request.sensitive_post_parameters = parameters
                else:
                    request.sensitive_post_parameters = "__ALL__"
                return view(request, *args, **kwargs)

        return sensitive_post_parameters_wrapper

    return decorator
