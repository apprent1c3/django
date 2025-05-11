from urllib.parse import quote

from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
)
from django.template import Context, Engine, TemplateDoesNotExist, loader
from django.views.decorators.csrf import requires_csrf_token

ERROR_404_TEMPLATE_NAME = "404.html"
ERROR_403_TEMPLATE_NAME = "403.html"
ERROR_400_TEMPLATE_NAME = "400.html"
ERROR_500_TEMPLATE_NAME = "500.html"
ERROR_PAGE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <title>%(title)s</title>
</head>
<body>
  <h1>%(title)s</h1><p>%(details)s</p>
</body>
</html>
"""


# These views can be called when CsrfViewMiddleware.process_view() not run,
# therefore need @requires_csrf_token in case the template needs
# {% csrf_token %}.


@requires_csrf_token
def page_not_found(request, exception, template_name=ERROR_404_TEMPLATE_NAME):
    """
    Handles HTTP 404 errors, rendering a custom error page with details about the requested URL and the exception that triggered the error.
    """
    exception_repr = exception.__class__.__name__
    # Try to get an "interesting" exception message, if any (and not the ugly
    # Resolver404 dictionary)
    try:
        message = exception.args[0]
    except (AttributeError, IndexError):
        pass
    else:
        if isinstance(message, str):
            exception_repr = message
    context = {
        "request_path": quote(request.path),
        "exception": exception_repr,
    }
    try:
        template = loader.get_template(template_name)
        body = template.render(context, request)
    except TemplateDoesNotExist:
        if template_name != ERROR_404_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        # Render template (even though there are no substitutions) to allow
        # inspecting the context in tests.
        template = Engine().from_string(
            ERROR_PAGE_TEMPLATE
            % {
                "title": "Not Found",
                "details": "The requested resource was not found on this server.",
            },
        )
        body = template.render(Context(context))
    return HttpResponseNotFound(body)


@requires_csrf_token
def server_error(request, template_name=ERROR_500_TEMPLATE_NAME):
    """
    Handles server errors by rendering a custom 500 error template. The template is loaded by name, and if it does not exist, a default error response is returned.
    """
    try:
        template = loader.get_template(template_name)
    except TemplateDoesNotExist:
        if template_name != ERROR_500_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        return HttpResponseServerError(
            ERROR_PAGE_TEMPLATE % {"title": "Server Error (500)", "details": ""},
        )
    return HttpResponseServerError(template.render())


@requires_csrf_token
def bad_request(request, exception, template_name=ERROR_400_TEMPLATE_NAME):
    """

    Handles HTTP 400 Bad Request errors, rendering a custom error template.

    The template used is configurable via the :attr:`template_name` parameter, defaulting to :data:`ERROR_400_TEMPLATE_NAME`.
    If the specified template does not exist, a default error page is displayed.

    """
    try:
        template = loader.get_template(template_name)
        body = template.render(request=request)
    except TemplateDoesNotExist:
        if template_name != ERROR_400_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        return HttpResponseBadRequest(
            ERROR_PAGE_TEMPLATE % {"title": "Bad Request (400)", "details": ""},
        )
    # No exception content is passed to the template, to not disclose any
    # sensitive information.
    return HttpResponseBadRequest(body)


@requires_csrf_token
def permission_denied(request, exception, template_name=ERROR_403_TEMPLATE_NAME):
    """
    Permission denied (403) handler, rendering a template with the exception message when available, or returning a default Http403 response.
    """
    try:
        template = loader.get_template(template_name)
    except TemplateDoesNotExist:
        if template_name != ERROR_403_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        return HttpResponseForbidden(
            ERROR_PAGE_TEMPLATE % {"title": "403 Forbidden", "details": ""},
        )
    return HttpResponseForbidden(
        template.render(request=request, context={"exception": str(exception)})
    )
