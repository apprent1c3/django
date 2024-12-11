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
        """

        Processes a view by returning a StreamingHttpResponse.

        This function generates a response that is sent back to the client in a streaming fashion,
        allowing for efficient handling of large amounts of data. The response is a redirect to an inner view,
        which is generated on the fly by reversing the 'inner' URL pattern.

        The response is created as a stream, allowing the data to be sent in chunks rather than all at once.
        This approach helps to reduce memory usage and improve performance, especially when dealing with large datasets.

        The function takes variable arguments (*args) and keyword arguments (**kwargs), which can be used to customize
        the behavior of the view processing and the generated response.

        """
        def stream():
            yield reverse("inner")

        return StreamingHttpResponse(stream())


class ReverseOuterInStreaming(MiddlewareMixin):
    def process_view(self, *args, **kwargs):
        """
        Processes a view and returns a StreamingHttpResponse.

        This method is used to handle HTTP requests and return a response that can be
        streamed back to the client. It generates a redirect to an 'outer' URL.

        Returns:
            StreamingHttpResponse: A response object that can be streamed to the client.

        Note:
            This method does not accept any positional or keyword arguments beyond
            those inherited from its parent class, but they are included in the method
            signature for compatibility and flexibility.

        """
        def stream():
            yield reverse("outer")

        return StreamingHttpResponse(stream())
