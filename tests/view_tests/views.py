import datetime
import decimal
import logging
import sys
from pathlib import Path

from django.core.exceptions import BadRequest, PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template import Context, Template, TemplateDoesNotExist
from django.urls import get_resolver
from django.views import View
from django.views.debug import (
    ExceptionReporter,
    SafeExceptionReporterFilter,
    technical_500_response,
)
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

TEMPLATES_PATH = Path(__file__).resolve().parent / "templates"


def index_page(request):
    """Dummy index page"""
    return HttpResponse("<html><body>Dummy page</body></html>")


def with_parameter(request, parameter):
    return HttpResponse("ok")


def raises(request):
    # Make sure that a callable that raises an exception in the stack frame's
    # local vars won't hijack the technical 500 response (#15025).
    def callable():
        raise Exception

    try:
        raise Exception
    except Exception:
        return technical_500_response(request, *sys.exc_info())


def raises500(request):
    # We need to inspect the HTML generated by the fancy 500 debug view but
    # the test client ignores it, so we send it explicitly.
    """
    Raises a 500 internal server error in response to the given request.

    This function intentionally triggers an exception and catches it, then returns a 
    technical 500 response based on the caught exception. It is intended for testing 
    or demonstration purposes, allowing for the simulation of server-side errors.

    :param request: The HTTP request object that triggered the error
    :rtype: HttpResponse
    :return: A technical 500 response object
    """
    try:
        raise Exception
    except Exception:
        return technical_500_response(request, *sys.exc_info())


class Raises500View(View):
    def get(self, request):
        try:
            raise Exception
        except Exception:
            return technical_500_response(request, *sys.exc_info())


def raises400(request):
    raise SuspiciousOperation


def raises400_bad_request(request):
    raise BadRequest("Malformed request syntax")


def raises403(request):
    raise PermissionDenied("Insufficient Permissions")


def raises404(request):
    """
    Simulates a request that raises a 404 error.

    This function tests the handling of requests to non-existent URLs by attempting to resolve a URL path that is not defined in the project's URL configuration.

    :returns: None
    :raises: Http404
    """
    resolver = get_resolver(None)
    resolver.resolve("/not-in-urls")


def technical404(request):
    raise Http404("Testing technical 404.")


class Http404View(View):
    def get(self, request):
        raise Http404("Testing class-based technical 404.")


def template_exception(request):
    return render(request, "debug/template_exception.html")


def safestring_in_template_exception(request):
    """
    Trigger an exception in the template machinery which causes a SafeString
    to be inserted as args[0] of the Exception.
    """
    template = Template('{% extends "<script>alert(1);</script>" %}')
    try:
        template.render(Context())
    except Exception:
        return technical_500_response(request, *sys.exc_info())


def jsi18n(request):
    return render(request, "jsi18n.html")


def jsi18n_multi_catalogs(request):
    return render(request, "jsi18n-multi-catalogs.html")


def raises_template_does_not_exist(request, path="i_dont_exist.html"):
    # We need to inspect the HTML generated by the fancy 500 debug view but
    # the test client ignores it, so we send it explicitly.
    try:
        return render(request, path)
    except TemplateDoesNotExist:
        return technical_500_response(request, *sys.exc_info())


def render_no_template(request):
    # If we do not specify a template, we need to make sure the debug
    # view doesn't blow up.
    return render(request, [], {})


def send_log(request, exc_info):
    """
    Sends an email to the site administrators with a server error report.

    This function logs an internal server error and sends an email notification to the admin using the Django admin email handler.
    The email includes the original request, error details, and a 500 status code.
    It temporarily disables any filters on the admin email handler to ensure the error email is sent, then restores the original filters afterwards.
    """
    logger = logging.getLogger("django")
    # The default logging config has a logging filter to ensure admin emails are
    # only sent with DEBUG=False, but since someone might choose to remove that
    # filter, we still want to be able to test the behavior of error emails
    # with DEBUG=True. So we need to remove the filter temporarily.
    admin_email_handler = [
        h for h in logger.handlers if h.__class__.__name__ == "AdminEmailHandler"
    ][0]
    orig_filters = admin_email_handler.filters
    admin_email_handler.filters = []
    admin_email_handler.include_html = True
    logger.error(
        "Internal Server Error: %s",
        request.path,
        exc_info=exc_info,
        extra={"status_code": 500, "request": request},
    )
    admin_email_handler.filters = orig_filters


def non_sensitive_view(request):
    # Do not just use plain strings for the variables' values in the code
    # so that the tests don't return false positives when the function's source
    # is displayed in the exception report.
    cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
    sauce = "".join(  # NOQA
        ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
    )
    try:
        raise Exception
    except Exception:
        exc_info = sys.exc_info()
        send_log(request, exc_info)
        return technical_500_response(request, *exc_info)


@sensitive_variables("sauce")
@sensitive_post_parameters("bacon-key", "sausage-key")
def sensitive_view(request):
    # Do not just use plain strings for the variables' values in the code
    # so that the tests don't return false positives when the function's source
    # is displayed in the exception report.
    cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
    sauce = "".join(  # NOQA
        ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
    )
    try:
        raise Exception
    except Exception:
        exc_info = sys.exc_info()
        send_log(request, exc_info)
        return technical_500_response(request, *exc_info)


@sensitive_variables("sauce")
@sensitive_post_parameters("bacon-key", "sausage-key")
async def async_sensitive_view(request):
    # Do not just use plain strings for the variables' values in the code so
    # that the tests don't return false positives when the function's source is
    # displayed in the exception report.
    """

    Asynchronous view function handling sensitive data and exceptions.

    This function processes incoming requests while protecting sensitive variables 
    and parameters. In case of an error, it logs the exception details and returns 
    a technical 500 response to the client.

    The sensitive variables and parameters in this view are masked to prevent 
    exposure in error messages or logs, specifically: 
    the 'sauce' variable and 'bacon-key' and 'sausage-key' POST parameters.

    It sends logged exceptions to the designated log handler, providing error 
    information without revealing sensitive data.

    :param request: The incoming HTTP request object
    :return: A technical 500 response in case of an exception, or none if the 
        function executes successfully

    """
    cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
    sauce = "".join(  # NOQA
        ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
    )
    try:
        raise Exception
    except Exception:
        exc_info = sys.exc_info()
        send_log(request, exc_info)
        return technical_500_response(request, *exc_info)


@sensitive_variables("sauce")
@sensitive_post_parameters("bacon-key", "sausage-key")
async def async_sensitive_function(request):
    # Do not just use plain strings for the variables' values in the code so
    # that the tests don't return false positives when the function's source is
    # displayed in the exception report.
    """

    Asynchronously performs a sensitive operation.

    This function is marked as sensitive and is therefore handled with extra caution.
    It protects specific request parameters and variables from being logged or exposed.

    The operation itself involves combining ingredients to create a meal, but it currently
    raises an exception and does not return a meaningful result.

    :raises Exception: Always raises an exception

    """
    cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
    sauce = "".join(  # NOQA
        ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
    )
    raise Exception


async def async_sensitive_view_nested(request):
    try:
        await async_sensitive_function(request)
    except Exception:
        exc_info = sys.exc_info()
        send_log(request, exc_info)
        return technical_500_response(request, *exc_info)


@sensitive_variables()
@sensitive_post_parameters()
def paranoid_view(request):
    # Do not just use plain strings for the variables' values in the code
    # so that the tests don't return false positives when the function's source
    # is displayed in the exception report.
    cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
    sauce = "".join(  # NOQA
        ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
    )
    try:
        raise Exception
    except Exception:
        exc_info = sys.exc_info()
        send_log(request, exc_info)
        return technical_500_response(request, *exc_info)


def sensitive_args_function_caller(request):
    try:
        sensitive_args_function(
            "".join(
                ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
            )
        )
    except Exception:
        exc_info = sys.exc_info()
        send_log(request, exc_info)
        return technical_500_response(request, *exc_info)


@sensitive_variables("sauce")
def sensitive_args_function(sauce):
    # Do not just use plain strings for the variables' values in the code
    # so that the tests don't return false positives when the function's source
    # is displayed in the exception report.
    cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
    raise Exception


def sensitive_kwargs_function_caller(request):
    try:
        sensitive_kwargs_function(
            "".join(
                ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
            )
        )
    except Exception:
        exc_info = sys.exc_info()
        send_log(request, exc_info)
        return technical_500_response(request, *exc_info)


@sensitive_variables("sauce")
def sensitive_kwargs_function(sauce=None):
    # Do not just use plain strings for the variables' values in the code
    # so that the tests don't return false positives when the function's source
    # is displayed in the exception report.
    cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
    raise Exception


class UnsafeExceptionReporterFilter(SafeExceptionReporterFilter):
    """
    Ignores all the filtering done by its parent class.
    """

    def get_post_parameters(self, request):
        return request.POST

    def get_traceback_frame_variables(self, request, tb_frame):
        return tb_frame.f_locals.items()


@sensitive_variables()
@sensitive_post_parameters()
def custom_exception_reporter_filter_view(request):
    # Do not just use plain strings for the variables' values in the code
    # so that the tests don't return false positives when the function's source
    # is displayed in the exception report.
    cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
    sauce = "".join(  # NOQA
        ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
    )
    request.exception_reporter_filter = UnsafeExceptionReporterFilter()
    try:
        raise Exception
    except Exception:
        exc_info = sys.exc_info()
        send_log(request, exc_info)
        return technical_500_response(request, *exc_info)


class CustomExceptionReporter(ExceptionReporter):
    custom_traceback_text = "custom traceback text"

    def get_traceback_html(self):
        return self.custom_traceback_text


class TemplateOverrideExceptionReporter(ExceptionReporter):
    html_template_path = TEMPLATES_PATH / "my_technical_500.html"
    text_template_path = TEMPLATES_PATH / "my_technical_500.txt"


def custom_reporter_class_view(request):
    """

    Trigger a custom exception reporter.

    This view intentionally raises an exception to test and demonstrate the custom exception reporter class.
    When invoked, it sets the exception reporter class to :class:`~CustomExceptionReporter`, simulates an exception, 
    and then returns a technical 500 response containing the exception details.

    .. note:: This view is intended for testing and debugging purposes only.

    """
    request.exception_reporter_class = CustomExceptionReporter
    try:
        raise Exception
    except Exception:
        exc_info = sys.exc_info()
        return technical_500_response(request, *exc_info)


class Klass:
    @sensitive_variables("sauce")
    def method(self, request):
        # Do not just use plain strings for the variables' values in the code
        # so that the tests don't return false positives when the function's
        # source is displayed in the exception report.
        """

        Handles a request, simulating preparation of scrambled eggs with a sauce, 
        and returns a technical 500 response when an exception occurs.

        The function prepares a representation of scrambled eggs and a sauce, 
        then intentionally raises an exception. The exception is caught and 
        used to construct a technical 500 response, which is returned along 
        with the request's information.

        Parameters
        ----------
        request : object
            The request object that is being handled.

        Returns
        -------
        object
            A technical 500 response based on the exception and request.

        """
        cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
        sauce = "".join(  # NOQA
            ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
        )
        try:
            raise Exception
        except Exception:
            exc_info = sys.exc_info()
            send_log(request, exc_info)
            return technical_500_response(request, *exc_info)

    @sensitive_variables("sauce")
    async def async_method(self, request):
        # Do not just use plain strings for the variables' values in the code
        # so that the tests don't return false positives when the function's
        # source is displayed in the exception report.
        cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
        sauce = "".join(  # NOQA
            ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
        )
        try:
            raise Exception
        except Exception:
            exc_info = sys.exc_info()
            send_log(request, exc_info)
            return technical_500_response(request, *exc_info)

    @sensitive_variables("sauce")
    async def _async_method_inner(self, request):
        # Do not just use plain strings for the variables' values in the code
        # so that the tests don't return false positives when the function's
        # source is displayed in the exception report.
        cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
        sauce = "".join(  # NOQA
            ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
        )
        raise Exception

    async def async_method_nested(self, request):
        try:
            await self._async_method_inner(request)
        except Exception:
            exc_info = sys.exc_info()
            send_log(request, exc_info)
            return technical_500_response(request, *exc_info)


def sensitive_method_view(request):
    return Klass().method(request)


async def async_sensitive_method_view(request):
    return await Klass().async_method(request)


async def async_sensitive_method_view_nested(request):
    return await Klass().async_method_nested(request)


@sensitive_variables("sauce")
@sensitive_post_parameters("bacon-key", "sausage-key")
def multivalue_dict_key_error(request):
    """
    Handle KeyError exceptions when accessing multivalue dictionaries.

    This function attempts to access a specific key in the request's POST data.
    If the key does not exist, it catches the resulting exception, logs the error,
    and returns a 500 Internal Server Error response to the client.

    The function also ensures sensitive variables and POST parameters are secured
    from exposure in error logs and responses. 

    Returns:
        A technical 500 response if a KeyError occurs when accessing the request's POST data.

    """
    cooked_eggs = "".join(["s", "c", "r", "a", "m", "b", "l", "e", "d"])  # NOQA
    sauce = "".join(  # NOQA
        ["w", "o", "r", "c", "e", "s", "t", "e", "r", "s", "h", "i", "r", "e"]
    )
    try:
        request.POST["bar"]
    except Exception:
        exc_info = sys.exc_info()
        send_log(request, exc_info)
        return technical_500_response(request, *exc_info)


def json_response_view(request):
    return JsonResponse(
        {
            "a": [1, 2, 3],
            "foo": {"bar": "baz"},
            # Make sure datetime and Decimal objects would be serialized properly
            "timestamp": datetime.datetime(2013, 5, 19, 20),
            "value": decimal.Decimal("3.14"),
        }
    )
