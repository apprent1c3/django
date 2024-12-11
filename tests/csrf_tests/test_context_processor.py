from django.http import HttpRequest
from django.template.context_processors import csrf
from django.test import SimpleTestCase

from .tests import CsrfFunctionTestMixin


class TestContextProcessor(CsrfFunctionTestMixin, SimpleTestCase):
    def test_force_token_to_string(self):
        """
        Tests that CSRF token is correctly forced to be treated as a string.

        This test case verifies that the CSRF token, even when initially set as a non-string 
        value (in this case, a string representation of a secret that could be 
        misinterpreted in certain contexts), is properly converted to a string when 
        retrieved from the token. The test uses a secret made up of a repeating character 
        to simulate a potential non-string value and checks that it is correctly masked 
        in the resulting token, confirming that the conversion to a string was successful 
        and secure. 
        """
        request = HttpRequest()
        test_secret = 32 * "a"
        request.META["CSRF_COOKIE"] = test_secret
        token = csrf(request).get("csrf_token")
        self.assertMaskedSecretCorrect(token, test_secret)
