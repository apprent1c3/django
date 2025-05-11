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
        Verifies that a HTTP response is a full response with the expected status code, content and headers.

        Checks the response status code, content, and if the request method is GET or HEAD, 
        also verifies the Last-Modified and ETag headers can be checked, but this check can be disabled.
        For other request methods, checks that Last-Modified and ETag headers are not present.
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
        Tests the If-Modified-Since HTTP header functionality.

        Verifies that the server responds correctly when the If-Modified-Since header is set to different values, 
        including a valid last modified date, a newer date, an invalid date, and an expired date.
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
        Tests the HTTP If-Unmodified-Since header functionality by sending GET requests 
        with different header values and verifying the corresponding responses.
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
        Tests the behavior of the HTTP client when the 'If-None-Match' header is used to make conditional requests, verifying that the client correctly handles both valid and expired ETags, as well as multiple ETags in the header.
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
        If-None-Match comparisons use weak matching, so weak and strong ETags
        with the same value result in a 304 response.
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

        Tests the handling of the If-None-Match header in HTTP requests.

        Verifies that a GET request with a \"*\" If-None-Match value returns a 304 
        Not Modified response, and that a subsequent PUT request returns a 412 
        Precondition Failed response. Also checks that a GET request to a resource 
        without an ETag returns a full response.

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
        Tests the client's handling of If-Match header requests to ensure conditional updates are properly validated against ETags, returning a Precondition Failed status code when the provided ETag is no longer valid.
        """
        self.client.defaults["HTTP_IF_MATCH"] = ETAG
        response = self.client.put("/condition/")
        self.assertFullResponse(response)
        self.client.defaults["HTTP_IF_MATCH"] = EXPIRED_ETAG
        response = self.client.put("/condition/")
        self.assertEqual(response.status_code, 412)

    def test_weak_if_match(self):
        """
        If-Match comparisons use strong matching, so any comparison involving
        a weak ETag return a 412 response.
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
        Tests that the If-Match header is evaluated correctly for HTTP requests, verifying that a request with a wildcard If-Match value succeeds when an ETag is present and fails with a 412 status code when no ETag is present.
        """
        self.client.defaults["HTTP_IF_MATCH"] = "*"
        response = self.client.get("/condition/")
        self.assertFullResponse(response)
        response = self.client.get("/condition/no_etag/")
        self.assertEqual(response.status_code, 412)

    def test_both_headers(self):
        # See RFC 9110 Section 13.2.2.
        """
        Tests the handling of HTTP conditional headers, specifically 'If-Modified-Since' and 'If-None-Match', to verify correct responses for both valid and expired header values.
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
        Tests HTTP conditional request headers, specifically 'If-Unmodified-Since' and 'If-Match', with various combinations of valid and expired values to ensure correct response status codes are returned.
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
        Tests conditional request handling for a single condition, specifically 
        If-Modified-Since and ETag headers, verifying that the server responds 
        correctly with 304 Not Modified and a full response respectively.
        """
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified/")
        self.assertNotModified(response)
        response = self.client.get("/condition/etag/")
        self.assertFullResponse(response, check_last_modified=False)

    def test_single_condition_2(self):
        """
        Tests the handling of single conditions, specifically the 'If-None-Match' header with an ETag, 
        to ensure that the server returns a '304 Not Modified' response when the client's ETag matches.
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
        Tests HTTP conditional requests with a single condition, ensuring that a 304 Not Modified response is returned when the If-Modified-Since header matches the last modified date, and a full response is returned for an unrelated condition (Etag).
        """
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified2/")
        self.assertNotModified(response)
        response = self.client.get("/condition/etag2/")
        self.assertFullResponse(response, check_last_modified=False)

    def test_single_condition_6(self):
        """
        Tests conditional GET requests with ETag and Last-Modified headers, verifying that the server responds appropriately with 304 Not Modified and 200 OK status codes respectively.
        """
        self.client.defaults["HTTP_IF_NONE_MATCH"] = ETAG
        response = self.client.get("/condition/etag2/")
        self.assertNotModified(response)
        response = self.client.get("/condition/last_modified2/")
        self.assertFullResponse(response, check_etag=False)

    def test_single_condition_7(self):
        """
        Tests that a single expired 'If-Unmodified-Since' header condition triggers a 412 response for both 'Last-Modified' and 'ETag' conditional requests.
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
        Tests HTTP requests with an expired If-Unmodified-Since header, verifying that the server returns a 412 status code for both last modified and etag conditional requests.
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
        Tests the handling of unquoted If-None-Match headers in HTTP requests.

        Verifies that the server correctly interprets and responds to If-None-Match headers
        with unquoted ETags, including returning 304 Not Modified and 412 Precondition Failed
        status codes as applicable.
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
