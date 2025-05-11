from datetime import datetime

from django.test import SimpleTestCase, override_settings

FULL_RESPONSE = "Test conditional get response"
LAST_MODIFIED = datetime(2007, 10, 21, 23, 21, 47)
LAST_MODIFIED_STR = "Sun, 21 Oct 2007 23:21:47 GMT"
LAST_MODIFIED_NEWER_STR = "Mon, 18 Oct 2010 16:56:23 GMT"
LAST_MODIFIED_INVALID_STR = "Mon, 32 Oct 2010 16:56:23 GMT"
EXPIRED_LAST_MODIFIED_STR = "Sat, 20 Oct 2007 23:21:47 GMT"
ETAG = '"b4246ffc4f62314ca13147c9d4f76974"'
WEAK_ETAG = 'W/"b4246ffc4f62314ca13147c9d4f76974"'  # weak match to ETAG
EXPIRED_ETAG = '"7fae4cd4b0f81e7d2914700043aa8ed6"'


@override_settings(ROOT_URLCONF="conditional_processing.urls")
class ConditionalGet(SimpleTestCase):
    def assertFullResponse(self, response, check_last_modified=True, check_etag=True):
        """

        Verifies that a response is a full response with expected headers and status code.

        Args:
            response: The response object to be checked.
            check_last_modified (bool): Whether to check the Last-Modified header. Defaults to True.
            check_etag (bool): Whether to check the ETag header. Defaults to True.

        Checks the response status code, content, and optionally Last-Modified and ETag headers if the request method is GET or HEAD.

        """
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, FULL_RESPONSE.encode())
        if response.request["REQUEST_METHOD"] in ("GET", "HEAD"):
            if check_last_modified:
                self.assertEqual(response.headers["Last-Modified"], LAST_MODIFIED_STR)
            if check_etag:
                self.assertEqual(response.headers["ETag"], ETAG)
        else:
            self.assertNotIn("Last-Modified", response.headers)
            self.assertNotIn("ETag", response.headers)

    def assertNotModified(self, response):
        self.assertEqual(response.status_code, 304)
        self.assertEqual(response.content, b"")

    def test_without_conditions(self):
        response = self.client.get("/condition/")
        self.assertFullResponse(response)

    def test_if_modified_since(self):
        """
        Tests the handling of the 'If-Modified-Since' HTTP header, verifying that 
         the server responds with 304 Not Modified when the requested resource has 
         not been modified since the specified date, and with a full response when 
         it has been modified or the header is invalid.
        """
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.get("/condition/")
        self.assertNotModified(response)
        response = self.client.put("/condition/")
        self.assertFullResponse(response)
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_NEWER_STR
        response = self.client.get("/condition/")
        self.assertNotModified(response)
        response = self.client.put("/condition/")
        self.assertFullResponse(response)
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_INVALID_STR
        response = self.client.get("/condition/")
        self.assertFullResponse(response)
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = EXPIRED_LAST_MODIFIED_STR
        response = self.client.get("/condition/")
        self.assertFullResponse(response)

    def test_if_unmodified_since(self):
        """
        Tests the behavior of the server when responding to HTTP requests with the 'If-Unmodified-Since' header, verifying the response status code for different header values.
        """
        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.get("/condition/")
        self.assertFullResponse(response)
        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = LAST_MODIFIED_NEWER_STR
        response = self.client.get("/condition/")
        self.assertFullResponse(response)
        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = LAST_MODIFIED_INVALID_STR
        response = self.client.get("/condition/")
        self.assertFullResponse(response)
        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = EXPIRED_LAST_MODIFIED_STR
        response = self.client.get("/condition/")
        self.assertEqual(response.status_code, 412)

    def test_if_none_match(self):
        """
        Tests conditional requests with the If-None-Match header, verifying that the server responds correctly when given a valid, expired, or multiple ETags.
        """
        self.client.defaults["HTTP_IF_NONE_MATCH"] = ETAG
        response = self.client.get("/condition/")
        self.assertNotModified(response)
        response = self.client.put("/condition/")
        self.assertEqual(response.status_code, 412)
        self.client.defaults["HTTP_IF_NONE_MATCH"] = EXPIRED_ETAG
        response = self.client.get("/condition/")
        self.assertFullResponse(response)

        # Several etags in If-None-Match is a bit exotic but why not?
        self.client.defaults["HTTP_IF_NONE_MATCH"] = "%s, %s" % (ETAG, EXPIRED_ETAG)
        response = self.client.get("/condition/")
        self.assertNotModified(response)

    def test_weak_if_none_match(self):
        """
        Tests the behavior of If-None-Match requests with weak ETags, verifying that they correctly result in 304 responses when matching.
        """
        self.client.defaults["HTTP_IF_NONE_MATCH"] = ETAG
        response = self.client.get("/condition/weak_etag/")
        self.assertNotModified(response)
        response = self.client.put("/condition/weak_etag/")
        self.assertEqual(response.status_code, 412)

        self.client.defaults["HTTP_IF_NONE_MATCH"] = WEAK_ETAG
        response = self.client.get("/condition/weak_etag/")
        self.assertNotModified(response)
        response = self.client.put("/condition/weak_etag/")
        self.assertEqual(response.status_code, 412)
        response = self.client.get("/condition/")
        self.assertNotModified(response)
        response = self.client.put("/condition/")
        self.assertEqual(response.status_code, 412)

    def test_all_if_none_match(self):
        """
        Tests conditional request handling for the '/condition/' and '/condition/no_etag/' endpoints, verifying that If-None-Match headers are correctly handled for both 304 Not Modified and 412 Precondition Failed responses.
        """
        self.client.defaults["HTTP_IF_NONE_MATCH"] = "*"
        response = self.client.get("/condition/")
        self.assertNotModified(response)
        response = self.client.put("/condition/")
        self.assertEqual(response.status_code, 412)
        response = self.client.get("/condition/no_etag/")
        self.assertFullResponse(response, check_last_modified=False, check_etag=False)

    def test_if_match(self):
        """
        Tests the behavior of the API when the If-Match header is provided, 
        verifying that a valid ETag allows a request to proceed, 
        while an expired ETag results in a 412 Precondition Failed response.
        """
        self.client.defaults["HTTP_IF_MATCH"] = ETAG
        response = self.client.put("/condition/")
        self.assertFullResponse(response)
        self.client.defaults["HTTP_IF_MATCH"] = EXPIRED_ETAG
        response = self.client.put("/condition/")
        self.assertEqual(response.status_code, 412)

    def test_weak_if_match(self):
        """
        Tests the behavior of the If-Match header with weak and strong ETags, verifying that a 412 response is returned for comparisons involving weak ETags.
        """
        self.client.defaults["HTTP_IF_MATCH"] = ETAG
        response = self.client.get("/condition/weak_etag/")
        self.assertEqual(response.status_code, 412)

        self.client.defaults["HTTP_IF_MATCH"] = WEAK_ETAG
        response = self.client.get("/condition/weak_etag/")
        self.assertEqual(response.status_code, 412)
        response = self.client.get("/condition/")
        self.assertEqual(response.status_code, 412)

    def test_all_if_match(self):
        """

        Tests the handling of HTTP If-Match header in conditional requests.

        Verifies that a GET request with a wildcard If-Match header ('*') succeeds 
        and returns a full response, while a request to a resource without an ETag 
        returns a 412 Precondition Failed status code.

        """
        self.client.defaults["HTTP_IF_MATCH"] = "*"
        response = self.client.get("/condition/")
        self.assertFullResponse(response)
        response = self.client.get("/condition/no_etag/")
        self.assertEqual(response.status_code, 412)

    def test_both_headers(self):
        # See RFC 9110 Section 13.2.2.
        """

        Tests HTTP requests with both If-Modified-Since and If-None-Match headers set,
        covering various scenarios of valid and expired cache control.

        """
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        self.client.defaults["HTTP_IF_NONE_MATCH"] = ETAG
        response = self.client.get("/condition/")
        self.assertNotModified(response)

        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = EXPIRED_LAST_MODIFIED_STR
        self.client.defaults["HTTP_IF_NONE_MATCH"] = ETAG
        response = self.client.get("/condition/")
        self.assertNotModified(response)

        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        self.client.defaults["HTTP_IF_NONE_MATCH"] = EXPIRED_ETAG
        response = self.client.get("/condition/")
        self.assertFullResponse(response)

        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = EXPIRED_LAST_MODIFIED_STR
        self.client.defaults["HTTP_IF_NONE_MATCH"] = EXPIRED_ETAG
        response = self.client.get("/condition/")
        self.assertFullResponse(response)

    def test_both_headers_2(self):
        """

        Tests the behavior of HTTP conditional requests with both 'If-Modified-Since' and 'If-Match' headers.
        Verifies the response status codes when both headers are valid, one or both are expired, or mismatched.

        """
        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = LAST_MODIFIED_STR
        self.client.defaults["HTTP_IF_MATCH"] = ETAG
        response = self.client.get("/condition/")
        self.assertFullResponse(response)

        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = EXPIRED_LAST_MODIFIED_STR
        self.client.defaults["HTTP_IF_MATCH"] = ETAG
        response = self.client.get("/condition/")
        self.assertFullResponse(response)

        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = EXPIRED_LAST_MODIFIED_STR
        self.client.defaults["HTTP_IF_MATCH"] = EXPIRED_ETAG
        response = self.client.get("/condition/")
        self.assertEqual(response.status_code, 412)

        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = LAST_MODIFIED_STR
        self.client.defaults["HTTP_IF_MATCH"] = EXPIRED_ETAG
        response = self.client.get("/condition/")
        self.assertEqual(response.status_code, 412)

    def test_single_condition_1(self):
        """
        Checks HTTP conditional request handling by verifying that a '304 Not Modified' response is returned when the 'If-Modified-Since' header matches the 'Last-Modified' header of the resource, and a full response is returned when checking an ETag.
        """
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified/")
        self.assertNotModified(response)
        response = self.client.get("/condition/etag/")
        self.assertFullResponse(response, check_last_modified=False)

    def test_single_condition_2(self):
        """
        Tests HTTP responses under single condition with If-None-Match header set, 
        verifying Not Modified response for etag condition and full response for last modified condition.
        """
        self.client.defaults["HTTP_IF_NONE_MATCH"] = ETAG
        response = self.client.get("/condition/etag/")
        self.assertNotModified(response)
        response = self.client.get("/condition/last_modified/")
        self.assertFullResponse(response, check_etag=False)

    def test_single_condition_3(self):
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = EXPIRED_LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified/")
        self.assertFullResponse(response, check_etag=False)

    def test_single_condition_4(self):
        self.client.defaults["HTTP_IF_NONE_MATCH"] = EXPIRED_ETAG
        response = self.client.get("/condition/etag/")
        self.assertFullResponse(response, check_last_modified=False)

    def test_single_condition_5(self):
        """
        Test the behavior of single conditions for HTTP requests, specifically 
        verifying correct handling of 'If-Modified-Since' and 'ETag' headers.
        """
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified2/")
        self.assertNotModified(response)
        response = self.client.get("/condition/etag2/")
        self.assertFullResponse(response, check_last_modified=False)

    def test_single_condition_6(self):
        """
        Tests conditional GET requests with If-None-Match and last modified headers, 
         verifying the not modified response for matching ETags and a full response 
         for last modified conditions.
        """
        self.client.defaults["HTTP_IF_NONE_MATCH"] = ETAG
        response = self.client.get("/condition/etag2/")
        self.assertNotModified(response)
        response = self.client.get("/condition/last_modified2/")
        self.assertFullResponse(response, check_etag=False)

    def test_single_condition_7(self):
        """
        Tests HTTP client behavior with a single expired If-Unmodified-Since header condition, 
        verifying that a 412 status code is returned for last modified and etag conditions.
        """
        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = EXPIRED_LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified/")
        self.assertEqual(response.status_code, 412)
        response = self.client.get("/condition/etag/")
        self.assertEqual(response.status_code, 412)

    def test_single_condition_8(self):
        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified/")
        self.assertFullResponse(response, check_etag=False)

    def test_single_condition_9(self):
        """
        Tests the HTTP client's behavior when sending a request with an expired If-Unmodified-Since header, 
        expecting a 412 Precondition Failed response from the server for both last modified and etag conditions.
        """
        self.client.defaults["HTTP_IF_UNMODIFIED_SINCE"] = EXPIRED_LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified2/")
        self.assertEqual(response.status_code, 412)
        response = self.client.get("/condition/etag2/")
        self.assertEqual(response.status_code, 412)

    def test_single_condition_head(self):
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.head("/condition/")
        self.assertNotModified(response)

    def test_unquoted(self):
        """
        The same quoted ETag should be set on the header regardless of whether
        etag_func() in condition() returns a quoted or an unquoted ETag.
        """
        response_quoted = self.client.get("/condition/etag/")
        response_unquoted = self.client.get("/condition/unquoted_etag/")
        self.assertEqual(response_quoted["ETag"], response_unquoted["ETag"])

    # It's possible that the matching algorithm could use the wrong value even
    # if the ETag header is set correctly correctly (as tested by
    # test_unquoted()), so check that the unquoted value is matched.
    def test_unquoted_if_none_match(self):
        """
        Checks the behavior of the client when handling unquoted If-None-Match headers, verifying that the server responds correctly with 304 Not Modified and 412 Precondition Failed status codes when the etag is valid and invalid respectively.
        """
        self.client.defaults["HTTP_IF_NONE_MATCH"] = ETAG
        response = self.client.get("/condition/unquoted_etag/")
        self.assertNotModified(response)
        response = self.client.put("/condition/unquoted_etag/")
        self.assertEqual(response.status_code, 412)
        self.client.defaults["HTTP_IF_NONE_MATCH"] = EXPIRED_ETAG
        response = self.client.get("/condition/unquoted_etag/")
        self.assertFullResponse(response, check_last_modified=False)

    def test_invalid_etag(self):
        self.client.defaults["HTTP_IF_NONE_MATCH"] = '"""'
        response = self.client.get("/condition/etag/")
        self.assertFullResponse(response, check_last_modified=False)
