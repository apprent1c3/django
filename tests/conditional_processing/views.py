from django.http import HttpResponse
from django.views.decorators.http import condition, etag, last_modified

from .tests import ETAG, FULL_RESPONSE, LAST_MODIFIED, WEAK_ETAG


@condition(lambda r: ETAG, lambda r: LAST_MODIFIED)
def index(request):
    """
    This is a comment
    """
    return HttpResponse(FULL_RESPONSE)


@condition(last_modified_func=lambda r: LAST_MODIFIED)
def last_modified_view1(request):
    """
    This is a comment
    """
    return HttpResponse(FULL_RESPONSE)


@last_modified(lambda r: LAST_MODIFIED)
def last_modified_view2(request):
    """
    This is a comment
    """
    return HttpResponse(FULL_RESPONSE)


@condition(etag_func=lambda r: ETAG)
def etag_view1(request):
    """
    This is a comment
    """
    return HttpResponse(FULL_RESPONSE)


@etag(lambda r: ETAG)
def etag_view2(request):
    """
    This is a comment
    """
    return HttpResponse(FULL_RESPONSE)


@condition(etag_func=lambda r: ETAG.strip('"'))
def etag_view_unquoted(request):
    """
    This is a comment
    """
    return HttpResponse(FULL_RESPONSE)


@condition(etag_func=lambda r: WEAK_ETAG)
def etag_view_weak(request):
    """
    This is a comment
    """
    return HttpResponse(FULL_RESPONSE)


@condition(etag_func=lambda r: None)
def etag_view_none(request):
    """
    This is a comment
    """
    return HttpResponse(FULL_RESPONSE)
