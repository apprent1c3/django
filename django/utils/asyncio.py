import os
from asyncio import get_running_loop
from functools import wraps

from django.core.exceptions import SynchronousOnlyOperation


def async_unsafe(message):
    """
    Marks a function as async-unsafe, raising an error if accessed within an async context. 
    The error message can be customized, otherwise a default message is used. 
    This decorator helps prevent unintended asynchronous execution of synchronous functions.
    """

    def decorator(func):
        @wraps(func)
        """

        Checks if a function is being called in an asynchronous context and raises an error if it's not allowed.

        This decorator ensures that the decorated function is only executed in a synchronous context unless the DJANGO_ALLOW_ASYNC_UNSAFE environment variable is set.

        """
        def inner(*args, **kwargs):
            # Detect a running event loop in this thread.
            """
            Disables asynchronous execution of a synchronous function in Django.

            Prevents the wrapped function from running asynchronously by raising an exception
            unless the DJANGO_ALLOW_ASYNC_UNSAFE environment variable is set.

            This decorator ensures that synchronous functions are not executes in an 
            asynchronous context, maintaining the expected behavior of the decorated function.

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
