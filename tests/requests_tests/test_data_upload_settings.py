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
        """

        Set up a test request with a sample payload for testing purposes.

        This method creates a WSGI request object with a POST method, 
        application/x-www-form-urlencoded content type, and a sample payload.
        The payload is a URL-encoded string with multiple values for the same key.
        The purpose of this setup is to provide a controlled environment for testing
        the handling of duplicate key values in URL-encoded form data.

        """
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
        """
        Tests the case when there is no limit on the maximum memory size for data uploads.

         Verifies the behavior of the system when the DATA_UPLOAD_MAX_MEMORY_SIZE setting is set to None.

         This test scenario helps ensure that the system can handle large uploads without any memory constraints.

         Returns:
            None
        """
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=None):
            self.request._load_post_and_files()


class DataUploadMaxMemorySizeMultipartPostTests(SimpleTestCase):
    def setUp(self):
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
        """
        Tests that an exception is raised when the request data exceeds the maximum allowed memory size.

        This test case simulates a request with data larger than the configured limit, verifying that a RequestDataTooBig exception is raised with the expected error message, ensuring proper handling of oversized data uploads.
        """
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=10):
            with self.assertRaisesMessage(RequestDataTooBig, TOO_MUCH_DATA_MSG):
                self.request._load_post_and_files()

    def test_size_not_exceeded(self):
        """
        Verifies that the maximum allowed memory size for data uploads is not exceeded.

        This test ensures that the DATA_UPLOAD_MAX_MEMORY_SIZE setting is enforced correctly,
        preventing large uploads from consuming excessive memory. It simulates a request with
        the maximum allowed memory size set to a specific value and checks that the request
        can be processed successfully without exceeding the memory limit.
        """
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=11):
            self.request._load_post_and_files()

    def test_no_limit(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=None):
            self.request._load_post_and_files()

    def test_file_passes(self):
        """
        Tests if a file passes the upload process when the request's memory size is limited.

        This test case simulates a POST request with a multipart/form-data payload containing a single file.
        It verifies that the uploaded file is correctly processed and available in the request's FILES dictionary, 
        even when the DATA_UPLOAD_MAX_MEMORY_SIZE setting is set to a low value, forcing the upload to be stored in a temporary file.
        The test checks for the presence of the uploaded file by its name ('file1') in the request's FILES dictionary.
        """
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
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=None):
            self.request.body

    def test_empty_content_length(self):
        self.request.environ["CONTENT_LENGTH"] = ""
        self.request.body


class DataUploadMaxNumberOfFieldsGet(SimpleTestCase):
    def test_get_max_fields_exceeded(self):
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
        """
        Sets up a mock WSGI request for testing purposes, simulating a POST request with a multipart/form-data payload.
        The request is configured with a specific boundary and contains two form data fields, `name1` and `name2`, with corresponding values `value1` and `value2`.
        This setup allows for testing of views and forms that handle multipart/form-data requests.
        """
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
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=2):
            self.request._load_post_and_files()

    def test_no_limit(self):
        """

        Tests the behavior of the request when there is no limit on the number of fields that can be uploaded.

        This test checks how the request handles data uploads when the DATA_UPLOAD_MAX_NUMBER_FIELDS setting is set to None,
        effectively removing any restrictions on the number of fields that can be uploaded.

        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=None):
            self.request._load_post_and_files()


class DataUploadMaxNumberOfFilesMultipartPost(SimpleTestCase):
    def setUp(self):
        """

        Sets up a test request for a multipart/form-data POST operation.

        This method prepares a WSGI request object with a fake payload, including multiple form data parts with filenames and values.
        The prepared request is stored as an instance attribute for further testing.

        """
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
        """
        Tests that an error is raised when the number of uploaded files exceeds the maximum allowed.

        This test case ensures that the application correctly handles cases where a user attempts to upload more files than the configured limit, 
        forcing the application to raise a TooManyFilesSent exception with a corresponding error message.
        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FILES=1):
            with self.assertRaisesMessage(TooManyFilesSent, TOO_MANY_FILES_MSG):
                self.request._load_post_and_files()

    def test_number_not_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FILES=2):
            self.request._load_post_and_files()

    def test_no_limit(self):
        """
        Tests the handling of file uploads when there is no limit on the number of files that can be uploaded.

        This test case verifies the behavior of the application when the DATA_UPLOAD_MAX_NUMBER_FILES setting is set to None,
         effectively removing any restrictions on the number of files that can be uploaded. The test checks that the request
         is properly loaded with post and file data in this scenario.
        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FILES=None):
            self.request._load_post_and_files()


class DataUploadMaxNumberOfFieldsFormPost(SimpleTestCase):
    def setUp(self):
        """
        Sets up a test request for a POST operation with a URL encoded payload.

        This function creates a mock request object with a specifically crafted payload, 
        containing a set of URL encoded key-value pairs. The payload includes repeated 
        keys with different values, allowing for testing of key duplication handling 
        in form data parsing.

        The test request is configured to mimic a POST operation with the 
        'application/x-www-form-urlencoded' content type, and a content length 
        matching the size of the provided payload.

        The resulting request object is stored as an instance attribute, making 
        it available for use in subsequent tests.\"\"\"
        ```
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
        """
        Tests that an exception is raised when the number of fields in a request exceeds the maximum allowed.

            This test validates the functionality of the DATA_UPLOAD_MAX_NUMBER_FIELDS setting by simulating a request
            with more fields than the allowed limit, verifying that a TooManyFieldsSent exception is raised with the
            expected error message. The goal is to ensure that the system properly handles and reports excessive field
            submissions to prevent potential security or performance issues. 
        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=2):
            with self.assertRaisesMessage(TooManyFieldsSent, TOO_MANY_FIELDS_MSG):
                self.request._load_post_and_files()

    def test_number_not_exceeded(self):
        """
        Tests that the maximum number of fields allowed in a data upload is not exceeded.

        Checks the functionality of the data upload process when the number of fields
        is limited. Verifies that the system behaves correctly when this limit is
        approached, ensuring that the upload process remains functional and secure.

        This test case specifically sets the maximum number of fields to 3 and then
        attempts to load post and file data, allowing the testing framework to evaluate
        the outcome and assert that the upload limit is enforced as expected.
        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=3):
            self.request._load_post_and_files()

    def test_no_limit(self):
        """

        Tests the request handling when there is no limit on the number of fields that can be uploaded.

        This test overrides the DATA_UPLOAD_MAX_NUMBER_FIELDS setting to None, effectively removing any limit on the number of fields.
        It then simulates the loading of post and file data from a request, verifying that the request can handle an unlimited number of fields.

        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=None):
            self.request._load_post_and_files()
