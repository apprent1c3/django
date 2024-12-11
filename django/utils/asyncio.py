import os
from asyncio import get_running_loop
from functools import wraps

from django.core.exceptions import SynchronousOnlyOperation


def async_unsafe(message):
    """
    Decorator to mark functions as async-unsafe. Someone trying to access
    the function while in an async context will get an error message.
    """

    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            # Detect a running event loop in this thread.
            """

            Inner function wrapper that checks for asynchronous operation in a synchronous context.

            Ensures the wrapped function is not executed in an event loop if the 'DJANGO_ALLOW_ASYNC_UNSAFE'
            environment variable is not set. If asynchronous operation is detected and the environment
            variable is not set, raises a SynchronousOnlyOperation exception. Otherwise, executes the 
            wrapped function with the provided arguments.

            :raises SynchronousOnlyOperation: if asynchronous operation is detected and 'DJANGO_ALLOW_ASYNC_UNSAFE' is not set
            :returns: result of the wrapped function execution

            """
            try:
                get_running_loop()
            except RuntimeError:
                pass
            else:
                if not os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                    raise SynchronousOnlyOperation(message)
            # Pass onward.
            return func(*args, **kwargs)

        return inner

    # If the message is actually a function, then be a no-arguments decorator.
    if callable(message):
        func = message
        message = (
            "You cannot call this from an async context - use a thread or "
            "sync_to_async."
        )
        return decorator(func)
    else:
        return decorator
