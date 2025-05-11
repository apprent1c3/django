from django.conf import settings
from django.contrib.flatpages.views import flatpage
from django.http import Http404
from django.utils.deprecation import MiddlewareMixin


class FlatpageFallbackMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        """
        Handles HTTP responses, particularly when the requested resource is not found (404 status code).
        If the status code is not 404, the original response is returned.
        Otherwise, attempts to serve a flatpage if available, or returns the original response if an error occurs.
        """
        if response.status_code != 404:
            return response  # No need to check for a flatpage for non-404 responses.
        try:
            return flatpage(request, request.path_info)
        # Return the original response if any errors happened. Because this
        # is a middleware, we can't assume the errors will be caught elsewhere.
        except Http404:
            return response
        except Exception:
            if settings.DEBUG:
                raise
            return response
