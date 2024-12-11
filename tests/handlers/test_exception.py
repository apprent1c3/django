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
        response = WSGIHandler()(self.get_suspicious_environ(), lambda *a, **k: None)
        self.assertEqual(response.status_code, 400)

    @override_settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=2)
    def test_data_upload_max_number_fields_exceeded(self):
        """

        Tests the behavior when the maximum number of fields allowed for data uploads is exceeded.

        Verifies that attempting to upload data with more fields than allowed results in a 400 Bad Request response.

        This test ensures the DATA_UPLOAD_MAX_NUMBER_FIELDS setting is enforced, preventing potential denial-of-service attacks.

        """
        response = WSGIHandler()(self.get_suspicious_environ(), lambda *a, **k: None)
        self.assertEqual(response.status_code, 400)

    @override_settings(DATA_UPLOAD_MAX_NUMBER_FILES=2)
    def test_data_upload_max_number_files_exceeded(self):
        """
        Tests that uploading more files than the allowed maximum number of files results in a 400 Bad Request response.
        The test verifies that the DATA_UPLOAD_MAX_NUMBER_FILES setting is enforced by attempting to upload more files than the specified limit.
        In this case, it checks that uploading three files exceeds the limit of two files and triggers an error response.
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
