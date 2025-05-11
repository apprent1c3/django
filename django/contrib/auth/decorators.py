import asyncio
from functools import wraps
from urllib.parse import urlsplit

from asgiref.sync import async_to_sync, sync_to_async

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.shortcuts import resolve_url


def user_passes_test(
    test_func, login_url=None, redirect_field_name=REDIRECT_FIELD_NAME
):
    """
    Checks if a user passes a specified test and redirects them to the login page if necessary, allowing for customizable login URLs and redirect fields.
    """

    def decorator(view_func):
        """
        Decorator that checks if a user passes a test function, redirecting to the login page if the test fails.

        :param view_func: The view function to decorate.
        :param login_url: The URL to redirect to if the test fails, defaults to settings.LOGIN_URL.
        :param redirect_field_name: The name of the field to store the redirect URL in the login form.
        :returns: The decorated view function, or a redirect to the login page if the test fails.
        """
        def _redirect_to_login(request):
            """
            Redirects an unauthenticated user to the login page, preserving the original request path if the login URL is on the same domain.
            """
            path = request.build_absolute_uri()
            resolved_login_url = resolve_url(login_url or settings.LOGIN_URL)
            # If the login url is the same scheme and net location then just
            # use the path as the "next" url.
            login_scheme, login_netloc = urlsplit(resolved_login_url)[:2]
            current_scheme, current_netloc = urlsplit(path)[:2]
            if (not login_scheme or login_scheme == current_scheme) and (
                not login_netloc or login_netloc == current_netloc
            ):
                path = request.get_full_path()
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(path, resolved_login_url, redirect_field_name)

        if asyncio.iscoroutinefunction(view_func):

            async def _view_wrapper(request, *args, **kwargs):
                """

                Wraps a view function to require user authentication and test function validation.

                Checks if the user is authenticated and then runs a test function to validate
                the user's access. If the test passes, the wrapped view function is executed.
                If the test fails or the user is not authenticated, redirects the user to the login page.

                """
                auser = await request.auser()
                if asyncio.iscoroutinefunction(test_func):
                    test_pass = await test_func(auser)
                else:
                    test_pass = await sync_to_async(test_func)(auser)

                if test_pass:
                    return await view_func(request, *args, **kwargs)
                return _redirect_to_login(request)

        else:

            def _view_wrapper(request, *args, **kwargs):
                """
                Checks user access rights by applying a test function and conditionally redirects to the login page if access is denied, otherwise calls the original view function.
                """
                if asyncio.iscoroutinefunction(test_func):
                    test_pass = async_to_sync(test_func)(request.user)
                else:
                    test_pass = test_func(request.user)

                if test_pass:
                    return view_func(request, *args, **kwargs)
                return _redirect_to_login(request)

        # Attributes used by LoginRequiredMiddleware.
        _view_wrapper.login_url = login_url
        _view_wrapper.redirect_field_name = redirect_field_name

        return wraps(view_func)(_view_wrapper)

    return decorator


def login_required(
    function=None, redirect_field_name=REDIRECT_FIELD_NAME, login_url=None
):
    """
    A decorator that ensures a view function can only be accessed by authenticated users, redirecting unauthenticated users to the login page.
    """
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated,
        login_url=login_url,
        redirect_field_name=redirect_field_name,
    )
    if function:
        return actual_decorator(function)
    return actual_decorator


def login_not_required(view_func):
    """
    Decorator for views that allows access to unauthenticated requests.
    """
    view_func.login_required = False
    return view_func


def permission_required(perm, login_url=None, raise_exception=False):
    """
    _checks whether a user has a particular permission, redirects to the log-in page if necessary, or raises a PermissionDenied exception if configured to do so_
    """
    if isinstance(perm, str):
        perms = (perm,)
    else:
        perms = perm

    def decorator(view_func):
        """
        Decorator that checks whether a user has the required permissions to access a view.

        This decorator supports both synchronous and asynchronous view functions, and allows
        for customizing the behavior when a user lacks the necessary permissions, including
        raising an exception or redirecting to a specified login URL.
        """
        if asyncio.iscoroutinefunction(view_func):

            async def check_perms(user):
                # First check if the user has the permission (even anon users).
                """
                Checks if a user has the required permissions, returning True if they do and False otherwise. If permission is denied and configured to do so, it raises a PermissionDenied exception.
                """
                if await sync_to_async(user.has_perms)(perms):
                    return True
                # In case the 403 handler should be called raise the exception.
                if raise_exception:
                    raise PermissionDenied
                # As the last resort, show the login form.
                return False

        else:

            def check_perms(user):
                # First check if the user has the permission (even anon users).
                """
                Checks if a user has the required permissions, raising a PermissionDenied exception if configured to do so.
                """
                if user.has_perms(perms):
                    return True
                # In case the 403 handler should be called raise the exception.
                if raise_exception:
                    raise PermissionDenied
                # As the last resort, show the login form.
                return False

        return user_passes_test(check_perms, login_url=login_url)(view_func)

    return decorator
