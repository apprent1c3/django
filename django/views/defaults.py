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
    This is a comment
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
    This is a comment
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
    This is a comment
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
    This is a comment
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
