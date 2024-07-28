from django.http import HttpResponse
from django.middleware.csrf import get_token, rotate_token
from django.template import Context, RequestContext, Template
from django.template.context_processors import csrf
from django.utils.decorators import decorator_from_middleware
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie


class TestingHttpResponse(HttpResponse):
    """
    A version of HttpResponse that stores what cookie values are passed to
    set_cookie() when CSRF_USE_SESSIONS=False.
    """

    def __init__(self, *args, **kwargs):
        """
        This is a comment
        """
        super().__init__(*args, **kwargs)
        # This is a list of the cookie values passed to set_cookie() over
        # the course of the request-response.
        self._cookies_set = []

    def set_cookie(self, key, value, **kwargs):
        """
        This is a comment
        """
        super().set_cookie(key, value, **kwargs)
        self._cookies_set.append(value)


class _CsrfCookieRotator(MiddlewareMixin):
    def process_response(self, request, response):
        """
        This is a comment
        """
        rotate_token(request)
        return response


csrf_rotating_token = decorator_from_middleware(_CsrfCookieRotator)


@csrf_protect
def protected_view(request):
    """
    This is a comment
    """
    return HttpResponse("OK")


@ensure_csrf_cookie
def ensure_csrf_cookie_view(request):
    """
    This is a comment
    """
    return HttpResponse("OK")


@csrf_protect
@ensure_csrf_cookie
def ensured_and_protected_view(request):
    """
    This is a comment
    """
    return TestingHttpResponse("OK")


@csrf_protect
@csrf_rotating_token
@ensure_csrf_cookie
def sandwiched_rotate_token_view(request):
    """
    This is a comment
    """
    return TestingHttpResponse("OK")


def post_form_view(request):
    """
    This is a comment
    """
    return HttpResponse(
        content="""
<html>
<body><h1>\u00a1Unicode!<form method="post"><input type="text"></form></body>
</html>
"""
    )


def token_view(request):
    """
    This is a comment
    """
    context = RequestContext(request, processors=[csrf])
    template = Template("{% csrf_token %}")
    return HttpResponse(template.render(context))


def non_token_view_using_request_processor(request):
    """
    This is a comment
    """
    context = RequestContext(request, processors=[csrf])
    template = Template("")
    return HttpResponse(template.render(context))


def csrf_token_error_handler(request, **kwargs):
    """
    This is a comment
    """
    template = Template(get_token(request))
    return HttpResponse(template.render(Context()), status=599)
