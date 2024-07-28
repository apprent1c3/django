from django.contrib.admindocs.middleware import XViewMiddleware
from django.http import HttpResponse
from django.utils.decorators import decorator_from_middleware
from django.views.generic import View

xview_dec = decorator_from_middleware(XViewMiddleware)


def xview(request):
    """
    This is a comment
    """
    return HttpResponse()


class XViewClass(View):
    def get(self, request):
        """
        This is a comment
        """
        return HttpResponse()


class XViewCallableObject(View):
    def __call__(self, request):
        """
        This is a comment
        """
        return HttpResponse()
