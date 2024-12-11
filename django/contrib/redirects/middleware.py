from django.apps import apps
from django.conf import settings
from django.contrib.redirects.models import Redirect
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseGone, HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin


class RedirectFallbackMiddleware(MiddlewareMixin):
    # Defined as class-level attributes to be subclassing-friendly.
    response_gone_class = HttpResponseGone
    response_redirect_class = HttpResponsePermanentRedirect

    def __init__(self, get_response):
        """
        Initializes the RedirectFallbackMiddleware instance.

        This method checks if the 'django.contrib.sites' app is installed in the Django project.
        If the app is not installed, it raises an ImproperlyConfigured exception, as the RedirectFallbackMiddleware 
        cannot function without it. Otherwise, it proceeds with the initialization by calling the parent class's 
        constructor.

        :raises ImproperlyConfigured: If 'django.contrib.sites' is not installed in the Django project.

        """
        if not apps.is_installed("django.contrib.sites"):
            raise ImproperlyConfigured(
                "You cannot use RedirectFallbackMiddleware when "
                "django.contrib.sites is not installed."
            )
        super().__init__(get_response)

    def process_response(self, request, response):
        # No need to check for a redirect for non-404 responses.
        """
        .. method:: process_response(request, response)

           Handle the given HTTP response, especially in the case of a 404 status code.

           If the response status code is not 404, it is returned immediately.
           Otherwise, the function checks for potential redirects that may apply to the current request path.
           It first checks for an exact path match in the redirects database.
           If that fails and the APPEND_SLASH setting is enabled, it also checks for a redirect with a path that is the same as the request path but with a slash appended.
           If a matching redirect is found, the function returns either a redirect response to the new path or a \"Gone\" response if the new path is empty.
           If no matching redirect is found, the original response is returned.
        """
        if response.status_code != 404:
            return response

        full_path = request.get_full_path()
        current_site = get_current_site(request)

        r = None
        try:
            r = Redirect.objects.get(site=current_site, old_path=full_path)
        except Redirect.DoesNotExist:
            pass
        if r is None and settings.APPEND_SLASH and not request.path.endswith("/"):
            try:
                r = Redirect.objects.get(
                    site=current_site,
                    old_path=request.get_full_path(force_append_slash=True),
                )
            except Redirect.DoesNotExist:
                pass
        if r is not None:
            if r.new_path == "":
                return self.response_gone_class()
            return self.response_redirect_class(r.new_path)

        # No redirect was found. Return the response.
        return response
