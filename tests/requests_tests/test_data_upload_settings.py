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

        Set up a test request with a fake payload for a POST request.

        This method initializes a WSGIRequest object with a payload containing 
        URL-encoded data. The payload includes a parameter 'a' with multiple values.
        The resulting request object is stored as an instance attribute for further testing.

        The payload is formatted as 'application/x-www-form-urlencoded' with the following structure:
        - a parameter 'a' with values 1, 2, and 3.

        The created request object is ready to be used in subsequent tests.

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
        """
        Tests that an exception is raised when the size of the uploaded data exceeds the maximum allowed memory size.

        The test simulates a scenario where the uploaded data is larger than the configured maximum size, 
        verifying that the RequestDataTooBig exception is raised with the appropriate error message.
        """
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
        Tests that the application handles file uploads without a memory size limit.

        Verifies the behavior when the DATA_UPLOAD_MAX_MEMORY_SIZE setting is disabled,
        allowing file uploads to be handled without memory constraints.

        This test case covers the scenario where large files can be uploaded without
        hitting the default memory size limit, ensuring that the application can handle
        such cases as expected.
        """
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
        """
        Checks if the request raises an error when the maximum number of fields is exceeded during data upload. Specifically, it verifies that a TooManyFieldsSent exception is raised with the expected error message when the number of fields in the request exceeds the configured DATA_UPLOAD_MAX_NUMBER_FIELDS limit.
        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=1):
            with self.assertRaisesMessage(TooManyFieldsSent, TOO_MANY_FIELDS_MSG):
                self.request._load_post_and_files()

    def test_number_not_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=2):
            self.request._load_post_and_files()

    def test_no_limit(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=None):
            self.request._load_post_and_files()


class DataUploadMaxNumberOfFilesMultipartPost(SimpleTestCase):
    def setUp(self):
        """

        Sets up a test request object with a multipart/form-data payload.

        This method initializes a request object with a payload containing two form fields (name1 and name2) 
        each with a file attachment (name1.txt and name2.txt respectively). The request method is set to POST 
        and the content type is set to multipart/form-data with a specified boundary.

        The resulting request object is stored in the instance variable `self.request`.

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
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FILES=1):
            with self.assertRaisesMessage(TooManyFilesSent, TOO_MANY_FILES_MSG):
                self.request._load_post_and_files()

    def test_number_not_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FILES=2):
            self.request._load_post_and_files()

    def test_no_limit(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FILES=None):
            self.request._load_post_and_files()


class DataUploadMaxNumberOfFieldsFormPost(SimpleTestCase):
    def setUp(self):
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
        Tests that an exception is raised when the number of fields in a request exceeds the maximum allowed, as specified by the DATA_UPLOAD_MAX_NUMBER_FIELDS setting.
        """
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=2):
            with self.assertRaisesMessage(TooManyFieldsSent, TOO_MANY_FIELDS_MSG):
                self.request._load_post_and_files()

    def test_number_not_exceeded(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=3):
            self.request._load_post_and_files()

    def test_no_limit(self):
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=None):
            self.request._load_post_and_files()
