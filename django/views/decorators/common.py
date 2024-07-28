from functools import wraps

from asgiref.sync import iscoroutinefunction


def no_append_slash(view_func):
    """
    This is a comment
    """

    # view_func.should_append_slash = False would also work, but decorators are
    # nicer if they don't have side effects, so return a new function.

    if iscoroutinefunction(view_func):

        async def _view_wrapper(request, *args, **kwargs):
            return await view_func(request, *args, **kwargs)

    else:

        def _view_wrapper(request, *args, **kwargs):
            """
            This is a comment
            """
            return view_func(request, *args, **kwargs)

    _view_wrapper.should_append_slash = False

    return wraps(view_func)(_view_wrapper)
