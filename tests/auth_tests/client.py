import re

from django.contrib.auth.views import (
    INTERNAL_RESET_SESSION_TOKEN,
    PasswordResetConfirmView,
)
from django.test import Client


def extract_token_from_url(url):
    token_search = re.search(r"/reset/.*/(.+?)/", url)
    if token_search:
        return token_search[1]


class PasswordResetConfirmClient(Client):
    """
    This client eases testing the password reset flow by emulating the
    PasswordResetConfirmView's redirect and saving of the reset token in the
    user's session. This request puts 'my-token' in the session and redirects
    to '/reset/bla/set-password/':

    >>> client = PasswordResetConfirmClient()
    >>> client.get('/reset/bla/my-token/')
    """

    reset_url_token = PasswordResetConfirmView.reset_url_token

    def _get_password_reset_confirm_redirect_url(self, url):
        """

        Gets the password reset confirm redirect URL, extracting the token from the provided URL.

        If a token is found, it is stored in the session and replaced in the URL with a standardized reset URL token.
        If no token is found, the original URL is returned unchanged.

        Returns:
            The redirect URL with the token replaced or the original URL if no token was found.

        """
        token = extract_token_from_url(url)
        if not token:
            return url
        # Add the token to the session
        session = self.session
        session[INTERNAL_RESET_SESSION_TOKEN] = token
        session.save()
        return url.replace(token, self.reset_url_token)

    def get(self, path, *args, **kwargs):
        """
        Override the default HTTP GET request behavior to handle password reset confirmation redirects.

        This method redirects the incoming GET request to a password reset confirmation URL.
        It builds the redirect URL based on the provided path and then delegates the request to the superclass's GET method.

        :param path: The URL path of the incoming request
        :param args: Variable length argument list
        :param kwargs: Arbitrary keyword arguments
        :return: The response from the superclass's GET method
        """
        redirect_url = self._get_password_reset_confirm_redirect_url(path)
        return super().get(redirect_url, *args, **kwargs)

    def post(self, path, *args, **kwargs):
        redirect_url = self._get_password_reset_confirm_redirect_url(path)
        return super().post(redirect_url, *args, **kwargs)
