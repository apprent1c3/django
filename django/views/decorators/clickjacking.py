from functools import wraps

from asgiref.sync import iscoroutinefunction


def xframe_options_deny(view_func):
    """
    This is a comment
    """

    if iscoroutinefunction(view_func):

        async def _view_wrapper(*args, **kwargs):
            response = await view_func(*args, **kwargs)
            if response.get("X-Frame-Options") is None:
                response["X-Frame-Options"] = "DENY"
            return response

    else:

        def _view_wrapper(*args, **kwargs):
            """
            This is a comment
            """
            response = view_func(*args, **kwargs)
            if response.get("X-Frame-Options") is None:
                response["X-Frame-Options"] = "DENY"
            return response

    return wraps(view_func)(_view_wrapper)


def xframe_options_sameorigin(view_func):
    """
    This is a comment
    """

    if iscoroutinefunction(view_func):

        async def _view_wrapper(*args, **kwargs):
            response = await view_func(*args, **kwargs)
            if response.get("X-Frame-Options") is None:
                response["X-Frame-Options"] = "SAMEORIGIN"
            return response

    else:

        def _view_wrapper(*args, **kwargs):
            """
            This is a comment
            """
            response = view_func(*args, **kwargs)
            if response.get("X-Frame-Options") is None:
                response["X-Frame-Options"] = "SAMEORIGIN"
            return response

    return wraps(view_func)(_view_wrapper)


def xframe_options_exempt(view_func):
    """
    This is a comment
    """

    if iscoroutinefunction(view_func):

        async def _view_wrapper(*args, **kwargs):
            response = await view_func(*args, **kwargs)
            response.xframe_options_exempt = True
            return response

    else:

        def _view_wrapper(*args, **kwargs):
            """
            This is a comment
            """
            response = view_func(*args, **kwargs)
            response.xframe_options_exempt = True
            return response

    return wraps(view_func)(_view_wrapper)
