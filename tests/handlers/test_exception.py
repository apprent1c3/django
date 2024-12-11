from django.core.handlers.wsgi import WSGIHandler
from django.test import SimpleTestCase, override_settings
from django.test.client import (
    BOUNDARY,
    MULTIPART_CONTENT,
    FakePayload,
    encode_multipart,
)


class ExceptionHandlerTests(SimpleTestCase):
    def get_suspicious_environ(self):
        payload = FakePayload("a=1&a=2&a=3\r\n")
        return {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": len(payload),
            "wsgi.input": payload,
            "SERVER_NAME": "test",
            "SERVER_PORT": "8000",
        }

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=12)
    def test_data_upload_max_memory_size_exceeded(self):
        """
        Tests the behavior when the maximum allowed memory size for data uploads is exceeded.

        This test case verifies that the application properly handles large data uploads by checking the HTTP response status code.

        The test scenario simulates an environment where the maximum allowed memory size for data uploads (DATA_UPLOAD_MAX_MEMORY_SIZE) is set to a certain threshold.

        It then asserts that when a data upload exceeds this threshold, the application returns a \"Bad Request\" response (HTTP status code 400).
        """
        response = WSGIHandler()(self.get_suspicious_environ(), lambda *a, **k: None)
        self.assertEqual(response.status_code, 400)

    @override_settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=2)
    def test_data_upload_max_number_fields_exceeded(self):
        response = WSGIHandler()(self.get_suspicious_environ(), lambda *a, **k: None)
        self.assertEqual(response.status_code, 400)

    @override_settings(DATA_UPLOAD_MAX_NUMBER_FILES=2)
    def test_data_upload_max_number_files_exceeded(self):
        """

        Tests the behavior when the maximum allowed number of files is exceeded during a data upload.

        This test case simulates a file upload with more files than the configured maximum, 
         checking that the server correctly returns a \"Bad Request\" response with a 400 status code.

        """
        payload = FakePayload(
            encode_multipart(
                BOUNDARY,
                {
                    "a.txt": "Hello World!",
                    "b.txt": "Hello Django!",
                    "c.txt": "Hello Python!",
                },
            )
        )
        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": MULTIPART_CONTENT,
            "CONTENT_LENGTH": len(payload),
            "wsgi.input": payload,
            "SERVER_NAME": "test",
            "SERVER_PORT": "8000",
        }

        response = WSGIHandler()(environ, lambda *a, **k: None)
        self.assertEqual(response.status_code, 400)
