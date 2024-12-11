"""
Clickjacking Protection Middleware.

This module provides a middleware that implements protection against a
malicious site loading resources from your site in a hidden frame.
"""

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class XFrameOptionsMiddleware(MiddlewareMixin):
    """
    Set the X-Frame-Options HTTP header in HTTP responses.

    Do not set the header if it's already set or if the response contains
    a xframe_options_exempt value set to True.

    By default, set the X-Frame-Options header to 'DENY', meaning the response
    cannot be displayed in a frame, regardless of the site attempting to do so.
    To enable the response to be loaded on a frame within the same site, set
    X_FRAME_OPTIONS in your project's Django settings to 'SAMEORIGIN'.
    """

    def process_response(self, request, response):
        # Don't set it if it's already in the response
        """
        Sets the X-Frame-Options header on a response to prevent clickjacking attacks, 
        unless the response is exempted or the header is already set. 

        The X-Frame-Options header value is determined based on the request and response data.
        If the response is already configured to allow or deny framing, 
        or if it has been explicitly exempted from this protection, 
        the function leaves the response unchanged. 

        Otherwise, it adds the X-Frame-Options header with a value determined by the 
        :getmeth:`get_xframe_options_value` method, using the request and response data as input. 

        :param request: The incoming request that triggered the response.
        :param response: The response to be modified.
        :return: The modified response with the X-Frame-Options header set, if applicable.
        """
        if response.get("X-Frame-Options") is not None:
            return response

        # Don't set it if they used @xframe_options_exempt
        if getattr(response, "xframe_options_exempt", False):
            return response

        response.headers["X-Frame-Options"] = self.get_xframe_options_value(
            request,
            response,
        )
        return response

    def get_xframe_options_value(self, request, response):
        """
        Get the value to set for the X_FRAME_OPTIONS header. Use the value from
        the X_FRAME_OPTIONS setting, or 'DENY' if not set.

        This method can be overridden if needed, allowing it to vary based on
        the request or response.
        """
        return getattr(settings, "X_FRAME_OPTIONS", "DENY").upper()
