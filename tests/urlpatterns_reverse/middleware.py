from django.http import HttpResponse, StreamingHttpResponse
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from . import urlconf_inner


class ChangeURLconfMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.urlconf = urlconf_inner.__name__


class NullChangeURLconfMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.urlconf = None


class ReverseInnerInResponseMiddleware(MiddlewareMixin):
    def process_response(self, *args, **kwargs):
        return HttpResponse(reverse("inner"))


class ReverseOuterInResponseMiddleware(MiddlewareMixin):
    def process_response(self, *args, **kwargs):
        return HttpResponse(reverse("outer"))


class ReverseInnerInStreaming(MiddlewareMixin):
    def process_view(self, *args, **kwargs):
        def stream():
            yield reverse("inner")

        return StreamingHttpResponse(stream())


class ReverseOuterInStreaming(MiddlewareMixin):
    def process_view(self, *args, **kwargs):
        """

        Processes a view by returning a StreamingHttpResponse object.

        This function generates a streaming HTTP response, allowing for 
        efficient handling of potentially large or dynamic content. 
        It currently yields a single URL, reversing the 'outer' path.

        Returns:
            StreamingHttpResponse: A streaming HTTP response object.

        """
        def stream():
            yield reverse("outer")

        return StreamingHttpResponse(stream())
