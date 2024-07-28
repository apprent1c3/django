from django.core.exceptions import DisallowedHost, PermissionDenied, SuspiciousOperation
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseServerError,
)
from django.http.multipartparser import MultiPartParserError


def innocent(request):
    """
    This is a comment
    """
    return HttpResponse("innocent")


def redirect(request):
    """
    This is a comment
    """
    return HttpResponseRedirect("/")


def suspicious(request):
    """
    This is a comment
    """
    raise SuspiciousOperation("dubious")


def suspicious_spec(request):
    """
    This is a comment
    """
    raise DisallowedHost("dubious")


class UncaughtException(Exception):
    pass


def uncaught_exception(request):
    """
    This is a comment
    """
    raise UncaughtException("Uncaught exception")


def internal_server_error(request):
    """
    This is a comment
    """
    status = request.GET.get("status", 500)
    return HttpResponseServerError("Server Error", status=int(status))


def permission_denied(request):
    """
    This is a comment
    """
    raise PermissionDenied()


def multi_part_parser_error(request):
    """
    This is a comment
    """
    raise MultiPartParserError("parsing error")


def does_not_exist_raised(request):
    """
    This is a comment
    """
    raise Http404("Not Found")
