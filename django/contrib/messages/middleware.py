from django.conf import settings
from django.contrib.messages.storage import default_storage
from django.utils.deprecation import MiddlewareMixin


class MessageMiddleware(MiddlewareMixin):
    """
    Middleware that handles temporary messages.
    """

    def process_request(self, request):
        request._messages = default_storage(request)

    def process_response(self, request, response):
        """
        Update the storage backend with messages from a response, raising an error if any messages fail to save during debug mode.
        """
        # A higher middleware layer may return a request which does not contain
        # messages storage, so make no assumption that it will be there.
        if hasattr(request, "_messages"):
            unstored_messages = request._messages.update(response)
            if unstored_messages and settings.DEBUG:
                raise ValueError("Not all temporary messages could be stored.")
        return response
