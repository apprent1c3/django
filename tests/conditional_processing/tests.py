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
        Verifies that the given HTTP response contains the expected full response content and appropriate headers.

        This function checks that the response status code is 200, and that the response content matches the expected full response.
        Additionally, it checks for the presence and correctness of 'Last-Modified' and 'ETag' headers in the response, 
        although these checks can be disabled by passing `check_last_modified=False` or `check_etag=False` respectively.

        The function handles different types of HTTP requests, and will not expect 'Last-Modified' and 'ETag' headers 
        to be present in responses to requests other than GET or HEAD.

        :param response: The HTTP response to be verified.
        :param check_last_modified: Whether to check the 'Last-Modified' header in the response. Defaults to True.
        :param check_etag: Whether to check the 'ETag' header in the response. Defaults to True.
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
        """
        Tests the retrieval of conditions without any filters or conditions.

        This test case sends a GET request to the '/condition/' endpoint and verifies that the response is complete and valid.

        Returns:
            None

        Raises:
            AssertionError: If the response is not complete or valid.
        """
        response = self.client.get("/condition/")
        self.assertFullResponse(response)

    def test_if_modified_since(self):
        """

        Test the conditional GET behavior of the API endpoint '/condition/' when the 
        'If-Modified-Since' header is provided.

        The test checks the following scenarios:
        - When the 'If-Modified-Since' header is set to a date that is the same as the 
          last modified date of the resource, the response should return a 304 Not Modified status.
        - When the 'If-Modified-Since' header is set to a date that is newer than the 
          last modified date of the resource, the response should return a 304 Not Modified status.
        - When the 'If-Modified-Since' header is set to an invalid date, the response 
          should return a full response.
        - When the 'If-Modified-Since' header is set to an expired date, the response 
          should return a full response.

        Verifies that the API correctly handles conditional GET requests based on the 
        'If-Modified-Since' header.

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
        Tests the HTTP If-None-Match header functionality.

        This test case verifies the behavior of the server when the client sends an If-None-Match header with different ETAG values.
        It checks the server's response in three scenarios: 
            when the ETAG matches the current resource version, 
            when the ETAG is expired, and 
            when multiple ETAGs are provided, including both matching and expired ones.

        The test ensures that the server returns the expected responses, including a 304 Not Modified status code when the ETAG matches, 
        a 412 Precondition Failed status code when the ETAG is expired, and a full response when the ETAG is invalid or expired.

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

        Tests the behavior of the server when handling If-None-Match headers.

        Verifies that the server responds correctly when the If-None-Match header is set to '*',
        which should result in a 304 Not Modified response for a GET request, a 412 Precondition Failed
        response for a PUT request, and a normal response for a resource that does not support etags.

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

        Tests the functionality of If-Match header in HTTP requests.

        Verifies that the API endpoint correctly handles the If-Match header by checking 
        the ETag of the requested resource. If the ETag matches, the request is successful.
        If the ETag does not match or is expired, the request returns a 412 Precondition Failed status code.

        This test case ensures that the API behaves as expected when handling concurrent 
        modifications to a resource, preventing data corruption or overwriting changes made by other users.

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

        Tests the HTTP If-Match header functionality.

        This test checks that a GET request to a resource with an ETag returns a full response
        when the If-Match header is set to '*'. It also verifies that a request to a resource
        without an ETag returns a 412 Precondition Failed status code when the If-Match header
        is set to '*'.

        """
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
        self.client.defaults["HTTP_IF_MODIFIED_SINCE"] = LAST_MODIFIED_STR
        response = self.client.get("/condition/last_modified/")
        self.assertNotModified(response)
        response = self.client.get("/condition/etag/")
        self.assertFullResponse(response, check_last_modified=False)

    def test_single_condition_2(self):
        """
        Tests the behavior of the client when making GET requests with a single condition specified via the If-None-Match header.

        The function verifies that the client correctly handles the response when the requested resource has not been modified, 
        by checking that a 304 Not Modified status is returned when the If-None-Match header matches the ETag of the resource.

        Additionally, it tests that the client can successfully retrieve a resource when the condition is not met, 
        by making a subsequent GET request to a different endpoint and verifying that a full response is returned.
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
        """
        Tests the response of a GET request to the '/condition/etag/' endpoint when an invalid ETag is provided in the 'If-None-Match' header.
        The function verifies that the server responds correctly to an invalid ETag by comparing the full response, excluding the last modified date.
        """
        self.client.defaults["HTTP_IF_NONE_MATCH"] = '"""'
        response = self.client.get("/condition/etag/")
        self.assertFullResponse(response, check_last_modified=False)
