from io import BytesIO

from django.core.exceptions import (
    RequestDataTooBig,
    TooManyFieldsSent,
    TooManyFilesSent,
)
from django.core.handlers.wsgi import WSGIRequest
from django.test import SimpleTestCase
from django.test.client import FakePayload

TOO_MANY_FIELDS_MSG = (
    "The number of GET/POST parameters exceeded settings.DATA_UPLOAD_MAX_NUMBER_FIELDS."
)
TOO_MANY_FILES_MSG = (
    "The number of files exceeded settings.DATA_UPLOAD_MAX_NUMBER_FILES."
)
TOO_MUCH_DATA_MSG = "Request body exceeded settings.DATA_UPLOAD_MAX_MEMORY_SIZE."


class DataUploadMaxMemorySizeFormPostTests(SimpleTestCase):
    def setUp(self):
        payload = FakePayload("a=1&a=2&a=3\r\n")
        self.request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )

    def test_size_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=12):
            with self.assertRaisesMessage(RequestDataTooBig, TOO_MUCH_DATA_MSG):
                self.request._load_post_and_files()

    def test_size_not_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=13):
            self.request._load_post_and_files()

    def test_no_limit(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=None):
            self.request._load_post_and_files()


class DataUploadMaxMemorySizeMultipartPostTests(SimpleTestCase):
    def setUp(self):
        """
        Setup a WSGI request object with a multipart/form-data payload for testing purposes.

        This method creates a fake HTTP request with a POST method, a content type of multipart/form-data, and a specific payload that contains a form field named \"name\" with a value of \"value\". The resulting request object is stored as an instance attribute.

        The purpose of this setup is to simulate a typical file or form upload request, allowing for testing of code that handles such requests. The specific details of the request, such as the content type and payload, are designed to mimic a real-world request as closely as possible.
        """
        payload = FakePayload(
            "\r\n".join(
                [
                    "--boundary",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "value",
                    "--boundary--",
                ]
            )
        )
        self.request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )

    def test_size_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=10):
            with self.assertRaisesMessage(RequestDataTooBig, TOO_MUCH_DATA_MSG):
                self.request._load_post_and_files()

    def test_size_not_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=11):
            self.request._load_post_and_files()

    def test_no_limit(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=None):
            self.request._load_post_and_files()

    def test_file_passes(self):
        payload = FakePayload(
            "\r\n".join(
                [
                    "--boundary",
                    'Content-Disposition: form-data; name="file1"; '
                    'filename="test.file"',
                    "",
                    "value",
                    "--boundary--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1):
            request._load_post_and_files()
            self.assertIn("file1", request.FILES, "Upload file not present")


class DataUploadMaxMemorySizeGetTests(SimpleTestCase):
    def setUp(self):
        self.request = WSGIRequest(
            {
                "REQUEST_METHOD": "GET",
                "wsgi.input": BytesIO(b""),
                "CONTENT_LENGTH": 3,
            }
        )

    def test_data_upload_max_memory_size_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=2):
            with self.assertRaisesMessage(RequestDataTooBig, TOO_MUCH_DATA_MSG):
                self.request.body

    def test_size_not_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=3):
            self.request.body

    def test_no_limit(self):
        """

        Tests the behavior when there is no limit imposed on the maximum memory size for data uploads.

        This test case verifies the functionality of the system when the DATA_UPLOAD_MAX_MEMORY_SIZE setting is set to None,
         effectively removing any restrictions on the size of uploaded data. It checks how the system handles requests with large
         or unlimited data payloads, providing insight into the handling of memory-intensive uploads.

        """
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=None):
            self.request.body

    def test_empty_content_length(self):
        """
        Tests the handling of an empty Content-Length header in the request.

        This test case verifies the behavior of the system when a request contains an empty Content-Length header.
        The expected outcome is described in the assertions within the test, ensuring that the system correctly handles this edge case.

        :raises: Any exceptions raised by the test case will be documented here when known.
        :returns: None
        """
        self.request.environ["CONTENT_LENGTH"] = ""
        self.request.body


class DataUploadMaxNumberOfFieldsGet(SimpleTestCase):
    def test_get_max_fields_exceeded(self):
        """

        Tests that an error is raised when the number of fields in a GET request exceeds the maximum allowed.

        The test simulates a GET request with multiple fields and verifies that a TooManyFieldsSent exception is raised with the expected error message when the DATA_UPLOAD_MAX_NUMBER_FIELDS setting is set to a value that is lower than the number of fields in the request.

        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=1):
            with self.assertRaisesMessage(TooManyFieldsSent, TOO_MANY_FIELDS_MSG):
                request = WSGIRequest(
                    {
                        "REQUEST_METHOD": "GET",
                        "wsgi.input": BytesIO(b""),
                        "QUERY_STRING": "a=1&a=2&a=3",
                    }
                )
                request.GET["a"]

    def test_get_max_fields_not_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=3):
            request = WSGIRequest(
                {
                    "REQUEST_METHOD": "GET",
                    "wsgi.input": BytesIO(b""),
                    "QUERY_STRING": "a=1&a=2&a=3",
                }
            )
            request.GET["a"]


class DataUploadMaxNumberOfFieldsMultipartPost(SimpleTestCase):
    def setUp(self):
        payload = FakePayload(
            "\r\n".join(
                [
                    "--boundary",
                    'Content-Disposition: form-data; name="name1"',
                    "",
                    "value1",
                    "--boundary",
                    'Content-Disposition: form-data; name="name2"',
                    "",
                    "value2",
                    "--boundary--",
                ]
            )
        )
        self.request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )

    def test_number_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=1):
            with self.assertRaisesMessage(TooManyFieldsSent, TOO_MANY_FIELDS_MSG):
                self.request._load_post_and_files()

    def test_number_not_exceeded(self):
        """
        Tests that the number of fields in a request does not exceed the maximum allowed.

        This test case verifies the enforcement of the DATA_UPLOAD_MAX_NUMBER_FIELDS setting,
        ensuring that the number of fields in a request is limited to the specified maximum.
        The test checks for the correct handling of requests when the field count is at the limit.

        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=2):
            self.request._load_post_and_files()

    def test_no_limit(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=None):
            self.request._load_post_and_files()


class DataUploadMaxNumberOfFilesMultipartPost(SimpleTestCase):
    def setUp(self):
        payload = FakePayload(
            "\r\n".join(
                [
                    "--boundary",
                    (
                        'Content-Disposition: form-data; name="name1"; '
                        'filename="name1.txt"'
                    ),
                    "",
                    "value1",
                    "--boundary",
                    (
                        'Content-Disposition: form-data; name="name2"; '
                        'filename="name2.txt"'
                    ),
                    "",
                    "value2",
                    "--boundary--",
                ]
            )
        )
        self.request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )

    def test_number_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FILES=1):
            with self.assertRaisesMessage(TooManyFilesSent, TOO_MANY_FILES_MSG):
                self.request._load_post_and_files()

    def test_number_not_exceeded(self):
        """
        Tests that the number of uploaded files does not exceed the maximum allowed.

        This test case sets the DATA_UPLOAD_MAX_NUMBER_FILES setting to 2 and then attempts to load post and file data from the request. 
        The purpose of this test is to ensure that the application correctly enforces the maximum number of file uploads.
        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FILES=2):
            self.request._load_post_and_files()

    def test_no_limit(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FILES=None):
            self.request._load_post_and_files()


class DataUploadMaxNumberOfFieldsFormPost(SimpleTestCase):
    def setUp(self):
        """

        Set up a test request object with a sample payload.

        This method creates a fake payload containing URL-encoded data, with multiple
        values for the same key. It then uses this payload to construct a WSGIRequest
        object, simulating a POST request with the payload as its body. The resulting
        request object is stored as an instance attribute, allowing it to be used in
        subsequent test cases.

        """
        payload = FakePayload("\r\n".join(["a=1&a=2&a=3", ""]))
        self.request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )

    def test_number_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=2):
            with self.assertRaisesMessage(TooManyFieldsSent, TOO_MANY_FIELDS_MSG):
                self.request._load_post_and_files()

    def test_number_not_exceeded(self):
        """

        Tests that the number of fields in a request does not exceed the maximum allowed limit.

        This test case verifies that the system correctly handles requests with a large number of fields.
        It checks that the request processing is stopped when the number of fields reaches the maximum limit defined in the settings.

        The test specifically checks the behavior when the maximum allowed number of fields is set to 3.

        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=3):
            self.request._load_post_and_files()

    def test_no_limit(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=None):
            self.request._load_post_and_files()
