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
        """
        Asserts that the given HTTP response is 'Not Modified'.

        Checks that the response status code is 304, indicating that the requested resource
        has not been modified, and that the response body is empty. This is useful for
        verifying that an HTTP request with a conditional header (e.g. If-None-Match or
        If-Modified-Since) is correctly handled by the server.

         Args:
            response: The HTTP response object to check.

         Raises:
            AssertionError: If the response status code is not 304 or the response body is not empty.
        """
        self.assertEqual(response.status_code, 304)
        self.assertEqual(response.content, b"")

    def test_without_conditions(self):
        """
        Tests retrieving conditions without any specific conditions.

        This test case verifies that the endpoint at '/condition/' returns a valid response.
        It checks the full response to ensure it matches the expected format and content,
        providing assurance that the endpoint is functioning correctly when no conditions are specified.
        """
        response = self.client.get("/condition/")
        self.assertFullResponse(response)

    def test_if_modified_since(self):
        """
        Tests the 'If-Modified-Since' HTTP header functionality in the client.

            This test case checks the client's behavior when sending a GET request with 
            the 'If-Modified-Since' header set to different values, including a 
            last-modified timestamp, a newer timestamp, an invalid timestamp, and an 
            expired timestamp. It verifies that the server responds correctly with a 
            304 Not Modified status when the requested resource has not been modified 
            since the given timestamp, and a full response when the resource has been 
            modified or the timestamp is invalid or expired.
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
        Tests the functionality of the If-Unmodified-Since request header.

        This test ensures that the server responds correctly when the If-Unmodified-Since 
        header is set to different values, including a valid date, a newer date, an invalid 
        date, and an expired date. The expected responses are verified, including a 
        Precondition Failed status code (412) when the date is expired.
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

        Tests the behavior of HTTP requests with the 'If-None-Match' header set to '*'.

        This test case covers three scenarios:
        1. A GET request to a resource with an ETag: Verifies that the response is not modified (304 status code).
        2. A PUT request to a resource with an ETag: Verifies that the request is rejected (412 status code) due to the '*' value in the 'If-None-Match' header.
        3. A GET request to a resource without an ETag: Verifies that the response is returned as expected, without considering the 'If-None-Match' header.

        Ensures proper handling of conditional requests and ETags by the server.

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
        Tests the handling of If-Match headers for update requests.

         The test checks the following scenarios:

         * A successful update when the provided ETag matches the expected one.
         * A failed update when the provided ETag is expired, resulting in a 412 status code.
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
        self.client.defaults["HTTP_IF_MATCH"] = "*"
        response = self.client.get("/condition/")
        self.assertFullResponse(response)
        response = self.client.get("/condition/no_etag/")
        self.assertEqual(response.status_code, 412)

    def test_both_headers(self):
        # See RFC 9110 Section 13.2.2.
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
        Test behavior of HTTP conditional requests with 'If-Modified-Since' and 'If-Match' headers.

        This test case evaluates the response of a GET request to the '/condition/' endpoint
        when both 'If-Modified-Since' and 'If-Match' headers are set. It checks the response
        for valid and expired header values, verifying that the server correctly handles
        conditional requests and returns the expected status codes.

        The test covers four scenarios:

        - A request with valid 'If-Modified-Since' and 'If-Match' headers.
        - A request with an expired 'If-Modified-Since' header and a valid 'If-Match' header.
        - A request with an expired 'If-Modified-Since' header and an expired 'If-Match' header,
          which is expected to return a conflict status code (412).
        - A request with a valid 'If-Modified-Since' header and an expired 'If-Match' header,
          also expected to return a conflict status code (412).

        By verifying the server's behavior under these conditions, this test ensures that the
        conditional request handling is implemented correctly and consistently with HTTP standards.
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

        Tests conditional HTTP requests based on single conditions.

        This test case checks the behavior of the API when handling conditional requests 
        with 'If-Modified-Since' and 'ETag' headers. Specifically, it verifies that 
        the server returns a 304 Not Modified response when the 'If-Modified-Since' 
        header is set and the requested resource has not been modified since the 
        specified date, and a full response when the 'ETag' header is used.

        """
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified/")
        self.assertNotModified(response)
        response = self.client.get("/condition/etag/")
        self.assertFullResponse(response, check_last_modified=False)

    def test_single_condition_2(self):
        """
        Test a scenario where a single condition is met for HTTP conditional requests.

        This test case verifies that when an If-None-Match header with a valid ETag is provided, 
        the server responds with a 304 Not Modified status code. Additionally, it checks that 
        when the If-None-Match header is not applicable, a full response is returned.
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
        """

        Tests a single condition where the HTTP IF_NONE_MATCH header is set to an expired ETag.

        Verifies that the client is able to correctly handle the expired ETag condition and 
        return the expected response from the server. The test checks the full response 
        from the server, excluding the last modified header.

        """
        self.client.defaults["HTTP_IF_NONE_MATCH"] = EXPIRED_ETAG
        response = self.client.get("/condition/etag/")
        self.assertFullResponse(response, check_last_modified=False)

    def test_single_condition_5(self):
        """
        Tests the handling of a single HTTP condition, specifically the \"If-Modified-Since\" header, 
        by sending a GET request to two different URLs. The test verifies that the server responds 
        with a 304 status code when the requested resource has not been modified since the specified 
        date, and that it returns a full response when no \"If-Modified-Since\" condition is met, 
        but an Etag is present instead.
        """
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified2/")
        self.assertNotModified(response)
        response = self.client.get("/condition/etag2/")
        self.assertFullResponse(response, check_last_modified=False)

    def test_single_condition_6(self):
        self.client.defaults["HTTP_IF_NONE_MATCH"] = ETAG
        response = self.client.get("/condition/etag2/")
        self.assertNotModified(response)
        response = self.client.get("/condition/last_modified2/")
        self.assertFullResponse(response, check_etag=False)

    def test_single_condition_7(self):
        """
        Tests that a single expired If-Unmodified-Since condition fails for both Last-Modified and ETag conditions.

        This test case verifies that when an expired If-Unmodified-Since header is set in the request, the server responds with a 412 Precondition Failed status code for both Last-Modified and ETag conditions, as expected.

        The test covers the scenario where a client has a cached version of a resource that is no longer valid due to changes on the server-side, ensuring that the client updates its cache accordingly.
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
        Tests the client's behavior when encountering a single condition (If-Unmodified-Since) with an expired value.

         This test case sets the If-Unmodified-Since header to an expired date and then sends GET requests to two different URLs, 
         checking that the server responds with a 412 Precondition Failed status code in both cases, 
         indicating that the requested resource has been modified since the specified date.
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
