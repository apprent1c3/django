from django.conf import settings
from django.contrib.flatpages.views import flatpage
from django.http import Http404
from django.utils.deprecation import MiddlewareMixin


class FlatpageFallbackMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        """
        Retrieves a response for the given request, handling 404 Not Found status codes by 
        attempting to retrieve a flatpage at the requested path. If a flatpage is found, it 
        is returned; otherwise, the original response is returned. In DEBUG mode, any 
        unexpected exceptions are raised; otherwise, they are caught and the original 
        response is returned.
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
