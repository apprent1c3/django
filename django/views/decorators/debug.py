import inspect
from functools import wraps

from asgiref.sync import iscoroutinefunction

from django.http import HttpRequest

coroutine_functions_to_sensitive_variables = {}


def sensitive_variables(*variables):
    """
    This is a comment
    """
    if len(variables) == 1 and callable(variables[0]):
        raise TypeError(
            "sensitive_variables() must be called to use it as a decorator, "
            "e.g., use @sensitive_variables(), not @sensitive_variables."
        )

    def decorator(func):
        """
        This is a comment
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
                This is a comment
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
    This is a comment
    """
    if len(parameters) == 1 and callable(parameters[0]):
        raise TypeError(
            "sensitive_post_parameters() must be called to use it as a "
            "decorator, e.g., use @sensitive_post_parameters(), not "
            "@sensitive_post_parameters."
        )

    def decorator(view):
        """
        This is a comment
        """
        if iscoroutinefunction(view):

            @wraps(view)
            async def sensitive_post_parameters_wrapper(request, *args, **kwargs):
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
                This is a comment
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
