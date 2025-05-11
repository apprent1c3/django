import base64
import hashlib
import os
import shutil
import sys
import tempfile as sys_tempfile
import unittest
from io import BytesIO, StringIO
from unittest import mock
from urllib.parse import quote

from django.conf import DEFAULT_STORAGE_ALIAS
from django.core.exceptions import SuspiciousFileOperation
from django.core.files import temp as tempfile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
from django.http.multipartparser import (
    FILE,
    MAX_TOTAL_HEADER_SIZE,
    MultiPartParser,
    MultiPartParserError,
    Parser,
)
from django.test import SimpleTestCase, TestCase, client, override_settings

from . import uploadhandler
from .models import FileModel

UNICODE_FILENAME = "test-0123456789_中文_Orléans.jpg"
MEDIA_ROOT = sys_tempfile.mkdtemp()
UPLOAD_FOLDER = "test_upload"
UPLOAD_TO = os.path.join(MEDIA_ROOT, UPLOAD_FOLDER)

CANDIDATE_TRAVERSAL_FILE_NAMES = [
    "/tmp/hax0rd.txt",  # Absolute path, *nix-style.
    "C:\\Windows\\hax0rd.txt",  # Absolute path, win-style.
    "C:/Windows/hax0rd.txt",  # Absolute path, broken-style.
    "\\tmp\\hax0rd.txt",  # Absolute path, broken in a different way.
    "/tmp\\hax0rd.txt",  # Absolute path, broken by mixing.
    "subdir/hax0rd.txt",  # Descendant path, *nix-style.
    "subdir\\hax0rd.txt",  # Descendant path, win-style.
    "sub/dir\\hax0rd.txt",  # Descendant path, mixed.
    "../../hax0rd.txt",  # Relative path, *nix-style.
    "..\\..\\hax0rd.txt",  # Relative path, win-style.
    "../..\\hax0rd.txt",  # Relative path, mixed.
    "..&#x2F;hax0rd.txt",  # HTML entities.
    "..&sol;hax0rd.txt",  # HTML entities.
]

CANDIDATE_INVALID_FILE_NAMES = [
    "/tmp/",  # Directory, *nix-style.
    "c:\\tmp\\",  # Directory, win-style.
    "/tmp/.",  # Directory dot, *nix-style.
    "c:\\tmp\\.",  # Directory dot, *nix-style.
    "/tmp/..",  # Parent directory, *nix-style.
    "c:\\tmp\\..",  # Parent directory, win-style.
    "",  # Empty filename.
]


@override_settings(
    MEDIA_ROOT=MEDIA_ROOT, ROOT_URLCONF="file_uploads.urls", MIDDLEWARE=[]
)
class FileUploadTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.makedirs(MEDIA_ROOT, exist_ok=True)
        cls.addClassCleanup(shutil.rmtree, MEDIA_ROOT)

    def test_upload_name_is_validated(self):
        """
        -tests that the :class:`UploadedFile` class correctly validates file names and raises a :class:`SuspiciousFileOperation` exception for potential security risks, such as attempting to upload files from the parent directory or a hidden directory.
        """
        candidates = [
            "/tmp/",
            "/tmp/..",
            "/tmp/.",
        ]
        if sys.platform == "win32":
            candidates.extend(
                [
                    "c:\\tmp\\",
                    "c:\\tmp\\..",
                    "c:\\tmp\\.",
                ]
            )
        for file_name in candidates:
            with self.subTest(file_name=file_name):
                self.assertRaises(SuspiciousFileOperation, UploadedFile, name=file_name)

    def test_simple_upload(self):
        with open(__file__, "rb") as fp:
            post_data = {
                "name": "Ringo",
                "file_field": fp,
            }
            response = self.client.post("/upload/", post_data)
        self.assertEqual(response.status_code, 200)

    def test_large_upload(self):
        """
        Tests the handling of large file uploads by sending a POST request with two files of significantly different sizes, one smaller than and one larger than the maximum allowed size, and verifies that the server responds with a successful status code (200).
        """
        file = tempfile.NamedTemporaryFile
        with file(suffix=".file1") as file1, file(suffix=".file2") as file2:
            file1.write(b"a" * (2**21))
            file1.seek(0)

            file2.write(b"a" * (10 * 2**20))
            file2.seek(0)

            post_data = {
                "name": "Ringo",
                "file_field1": file1,
                "file_field2": file2,
            }

            for key in list(post_data):
                try:
                    post_data[key + "_hash"] = hashlib.sha1(
                        post_data[key].read()
                    ).hexdigest()
                    post_data[key].seek(0)
                except AttributeError:
                    post_data[key + "_hash"] = hashlib.sha1(
                        post_data[key].encode()
                    ).hexdigest()

            response = self.client.post("/verify/", post_data)

            self.assertEqual(response.status_code, 200)

    def _test_base64_upload(self, content, encode=base64.b64encode):
        """
        Tests the ability to upload a file encoded in base64 via a multipart form request.
        """
        payload = client.FakePayload(
            "\r\n".join(
                [
                    "--" + client.BOUNDARY,
                    'Content-Disposition: form-data; name="file"; filename="test.txt"',
                    "Content-Type: application/octet-stream",
                    "Content-Transfer-Encoding: base64",
                    "",
                ]
            )
        )
        payload.write(b"\r\n" + encode(content.encode()) + b"\r\n")
        payload.write("--" + client.BOUNDARY + "--\r\n")
        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/echo_content/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        self.assertEqual(response.json()["file"], content)

    def test_base64_upload(self):
        self._test_base64_upload("This data will be transmitted base64-encoded.")

    def test_big_base64_upload(self):
        self._test_base64_upload("Big data" * 68000)  # > 512Kb

    def test_big_base64_newlines_upload(self):
        self._test_base64_upload("Big data" * 68000, encode=base64.encodebytes)

    def test_base64_invalid_upload(self):
        """
        Tests the server's response to an invalid base64 encoded file upload, verifying that it correctly handles malformed input and returns an empty file.
        """
        payload = client.FakePayload(
            "\r\n".join(
                [
                    "--" + client.BOUNDARY,
                    'Content-Disposition: form-data; name="file"; filename="test.txt"',
                    "Content-Type: application/octet-stream",
                    "Content-Transfer-Encoding: base64",
                    "",
                ]
            )
        )
        payload.write(b"\r\n!\r\n")
        payload.write("--" + client.BOUNDARY + "--\r\n")
        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/echo_content/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        self.assertEqual(response.json()["file"], "")

    def test_unicode_file_name(self):
        """
        Tests uploading a file with a Unicode filename to ensure successful processing.
        """
        with sys_tempfile.TemporaryDirectory() as temp_dir:
            # This file contains Chinese symbols and an accented char in the name.
            with open(os.path.join(temp_dir, UNICODE_FILENAME), "w+b") as file1:
                file1.write(b"b" * (2**10))
                file1.seek(0)
                response = self.client.post("/unicode_name/", {"file_unicode": file1})
            self.assertEqual(response.status_code, 200)

    def test_unicode_file_name_rfc2231(self):
        """
        Tests the handling of file uploads with Unicode filenames encoded according to RFC 2231.
        """
        payload = client.FakePayload()
        payload.write(
            "\r\n".join(
                [
                    "--" + client.BOUNDARY,
                    'Content-Disposition: form-data; name="file_unicode"; '
                    "filename*=UTF-8''%s" % quote(UNICODE_FILENAME),
                    "Content-Type: application/octet-stream",
                    "",
                    "You got pwnd.\r\n",
                    "\r\n--" + client.BOUNDARY + "--\r\n",
                ]
            )
        )

        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/unicode_name/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        self.assertEqual(response.status_code, 200)

    def test_unicode_name_rfc2231(self):
        """
        Tests handling of file uploads with Unicode filenames encoded according to RFC 2231.
        """
        payload = client.FakePayload()
        payload.write(
            "\r\n".join(
                [
                    "--" + client.BOUNDARY,
                    "Content-Disposition: form-data; name*=UTF-8''file_unicode; "
                    "filename*=UTF-8''%s" % quote(UNICODE_FILENAME),
                    "Content-Type: application/octet-stream",
                    "",
                    "You got pwnd.\r\n",
                    "\r\n--" + client.BOUNDARY + "--\r\n",
                ]
            )
        )

        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/unicode_name/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        self.assertEqual(response.status_code, 200)

    def test_unicode_file_name_rfc2231_with_double_quotes(self):
        """
        Tests a POST request with a multipart form data containing a file, ensuring correct handling of a file with a Unicode name, encoded according to RFC 2231, and including double quotes in the filename. Verifies the server responds with a 200 status code.
        """
        payload = client.FakePayload()
        payload.write(
            "\r\n".join(
                [
                    "--" + client.BOUNDARY,
                    'Content-Disposition: form-data; name="file_unicode"; '
                    "filename*=\"UTF-8''%s\"" % quote(UNICODE_FILENAME),
                    "Content-Type: application/octet-stream",
                    "",
                    "You got pwnd.\r\n",
                    "\r\n--" + client.BOUNDARY + "--\r\n",
                ]
            )
        )
        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/unicode_name/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        self.assertEqual(response.status_code, 200)

    def test_unicode_name_rfc2231_with_double_quotes(self):
        """
        Tests handling of a multipart form upload with a Unicode filename containing double quotes, following the guidelines of RFC 2231, to ensure correct parsing and processing of the request.
        """
        payload = client.FakePayload()
        payload.write(
            "\r\n".join(
                [
                    "--" + client.BOUNDARY,
                    "Content-Disposition: form-data; name*=\"UTF-8''file_unicode\"; "
                    "filename*=\"UTF-8''%s\"" % quote(UNICODE_FILENAME),
                    "Content-Type: application/octet-stream",
                    "",
                    "You got pwnd.\r\n",
                    "\r\n--" + client.BOUNDARY + "--\r\n",
                ]
            )
        )
        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/unicode_name/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        self.assertEqual(response.status_code, 200)

    def test_blank_filenames(self):
        """
        Tests the handling of file uploads with blank or invalid filenames, verifying that the server accepts these uploads without errors.
        """
        filenames = [
            "",
            # Normalized by MultiPartParser.IE_sanitize().
            "C:\\Windows\\",
            # Normalized by os.path.basename().
            "/",
            "ends-with-slash/",
        ]
        payload = client.FakePayload()
        for i, name in enumerate(filenames):
            payload.write(
                "\r\n".join(
                    [
                        "--" + client.BOUNDARY,
                        'Content-Disposition: form-data; name="file%s"; filename="%s"'
                        % (i, name),
                        "Content-Type: application/octet-stream",
                        "",
                        "You got pwnd.\r\n",
                    ]
                )
            )
        payload.write("\r\n--" + client.BOUNDARY + "--\r\n")

        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/echo/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        self.assertEqual(response.status_code, 200)

        # Empty filenames should be ignored
        received = response.json()
        for i, name in enumerate(filenames):
            self.assertIsNone(received.get("file%s" % i))

    def test_non_printable_chars_in_file_names(self):
        """
        Tests the handling of non-printable characters in file names during file uploads, ensuring they are properly sanitized and do not cause issues with the upload process.
        """
        file_name = "non-\x00printable\x00\n_chars.txt\x00"
        payload = client.FakePayload()
        payload.write(
            "\r\n".join(
                [
                    "--" + client.BOUNDARY,
                    f'Content-Disposition: form-data; name="file"; '
                    f'filename="{file_name}"',
                    "Content-Type: application/octet-stream",
                    "",
                    "You got pwnd.\r\n",
                ]
            )
        )
        payload.write("\r\n--" + client.BOUNDARY + "--\r\n")
        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/echo/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        # Non-printable chars are sanitized.
        received = response.json()
        self.assertEqual(received["file"], "non-printable_chars.txt")

    def test_dangerous_file_names(self):
        """
        Tests if the application properly sanitizes uploaded file names to prevent directory traversal attacks, ensuring that all uploaded files are given a safe default name.
        """
        # This test simulates possible directory traversal attacks by a
        # malicious uploader We have to do some monkeybusiness here to construct
        # a malicious payload with an invalid file name (containing os.sep or
        # os.pardir). This similar to what an attacker would need to do when
        # trying such an attack.
        payload = client.FakePayload()
        for i, name in enumerate(CANDIDATE_TRAVERSAL_FILE_NAMES):
            payload.write(
                "\r\n".join(
                    [
                        "--" + client.BOUNDARY,
                        'Content-Disposition: form-data; name="file%s"; filename="%s"'
                        % (i, name),
                        "Content-Type: application/octet-stream",
                        "",
                        "You got pwnd.\r\n",
                    ]
                )
            )
        payload.write("\r\n--" + client.BOUNDARY + "--\r\n")

        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/echo/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        # The filenames should have been sanitized by the time it got to the view.
        received = response.json()
        for i, name in enumerate(CANDIDATE_TRAVERSAL_FILE_NAMES):
            got = received["file%s" % i]
            self.assertEqual(got, "hax0rd.txt")

    def test_filename_overflow(self):
        """
        Tests the handling of file names exceeding 256 characters, verifying they are truncated to avoid potential platform-specific issues.
        """
        long_str = "f" * 300
        cases = [
            # field name, filename, expected
            ("long_filename", "%s.txt" % long_str, "%s.txt" % long_str[:251]),
            ("long_extension", "foo.%s" % long_str, ".%s" % long_str[:254]),
            ("no_extension", long_str, long_str[:255]),
            ("no_filename", ".%s" % long_str, ".%s" % long_str[:254]),
            ("long_everything", "%s.%s" % (long_str, long_str), ".%s" % long_str[:254]),
        ]
        payload = client.FakePayload()
        for name, filename, _ in cases:
            payload.write(
                "\r\n".join(
                    [
                        "--" + client.BOUNDARY,
                        'Content-Disposition: form-data; name="{}"; filename="{}"',
                        "Content-Type: application/octet-stream",
                        "",
                        "Oops.",
                        "",
                    ]
                ).format(name, filename)
            )
        payload.write("\r\n--" + client.BOUNDARY + "--\r\n")
        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/echo/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        result = response.json()
        for name, _, expected in cases:
            got = result[name]
            self.assertEqual(expected, got, "Mismatch for {}".format(name))
            self.assertLess(
                len(got), 256, "Got a long file name (%s characters)." % len(got)
            )

    def test_file_content(self):
        """
        Tests the server's ability to handle file content from different sources by uploading files with and without content types, as well as string and byte streams, and verifies that the server correctly echoes the content back in its response.
        """
        file = tempfile.NamedTemporaryFile
        with (
            file(suffix=".ctype_extra") as no_content_type,
            file(suffix=".ctype_extra") as simple_file,
        ):
            no_content_type.write(b"no content")
            no_content_type.seek(0)

            simple_file.write(b"text content")
            simple_file.seek(0)
            simple_file.content_type = "text/plain"

            string_io = StringIO("string content")
            bytes_io = BytesIO(b"binary content")

            response = self.client.post(
                "/echo_content/",
                {
                    "no_content_type": no_content_type,
                    "simple_file": simple_file,
                    "string": string_io,
                    "binary": bytes_io,
                },
            )
            received = response.json()
            self.assertEqual(received["no_content_type"], "no content")
            self.assertEqual(received["simple_file"], "text content")
            self.assertEqual(received["string"], "string content")
            self.assertEqual(received["binary"], "binary content")

    def test_content_type_extra(self):
        """
        Tests handling of uploaded files with extra content type parameters.

        Verifies that files without content type parameters are handled correctly, and
        that files with content type parameters have those parameters properly extracted
        and returned in the response.
        """
        file = tempfile.NamedTemporaryFile
        with (
            file(suffix=".ctype_extra") as no_content_type,
            file(suffix=".ctype_extra") as simple_file,
        ):
            no_content_type.write(b"something")
            no_content_type.seek(0)

            simple_file.write(b"something")
            simple_file.seek(0)
            simple_file.content_type = "text/plain; test-key=test_value"

            response = self.client.post(
                "/echo_content_type_extra/",
                {
                    "no_content_type": no_content_type,
                    "simple_file": simple_file,
                },
            )
            received = response.json()
            self.assertEqual(received["no_content_type"], {})
            self.assertEqual(received["simple_file"], {"test-key": "test_value"})

    def test_truncated_multipart_handled_gracefully(self):
        """
        Tests that the MultiPartParser handles incomplete multipart messages gracefully, without attempting to read beyond the end of the stream.
        """
        payload_str = "\r\n".join(
            [
                "--" + client.BOUNDARY,
                'Content-Disposition: form-data; name="file"; filename="foo.txt"',
                "Content-Type: application/octet-stream",
                "",
                "file contents" "--" + client.BOUNDARY + "--",
                "",
            ]
        )
        payload = client.FakePayload(payload_str[:-10])
        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/echo/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        self.assertEqual(self.client.request(**r).json(), {})

    def test_empty_multipart_handled_gracefully(self):
        """
        If passed an empty multipart message, MultiPartParser will return
        an empty QueryDict.
        """
        r = {
            "CONTENT_LENGTH": 0,
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/echo/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": client.FakePayload(b""),
        }
        self.assertEqual(self.client.request(**r).json(), {})

    def test_custom_upload_handler(self):
        """
        Tests the custom upload handler's functionality in enforcing file size limits, ensuring that files within the allowed quota are successfully uploaded while larger files are rejected.
        """
        file = tempfile.NamedTemporaryFile
        with file() as smallfile, file() as bigfile:
            # A small file (under the 5M quota)
            smallfile.write(b"a" * (2**21))
            smallfile.seek(0)

            # A big file (over the quota)
            bigfile.write(b"a" * (10 * 2**20))
            bigfile.seek(0)

            # Small file posting should work.
            self.assertIn("f", self.client.post("/quota/", {"f": smallfile}).json())

            # Large files don't go through.
            self.assertNotIn("f", self.client.post("/quota/", {"f": bigfile}).json())

    def test_broken_custom_upload_handler(self):
        """
        Tests that attempting to alter the custom upload handler after an upload has been processed raises an AttributeError with the expected error message.
        """
        with tempfile.NamedTemporaryFile() as file:
            file.write(b"a" * (2**21))
            file.seek(0)

            msg = (
                "You cannot alter upload handlers after the upload has been processed."
            )
            with self.assertRaisesMessage(AttributeError, msg):
                self.client.post("/quota/broken/", {"f": file})

    def test_stop_upload_temporary_file_handler(self):
        """
        Testing the deletion of a temporary file after stopping an upload, ensuring that the file is removed from the file system after the stop upload request is completed.
        """
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(b"a")
            temp_file.seek(0)
            response = self.client.post("/temp_file/stop_upload/", {"file": temp_file})
            temp_path = response.json()["temp_path"]
            self.assertIs(os.path.exists(temp_path), False)

    def test_upload_interrupted_temporary_file_handler(self):
        # Simulate an interrupted upload by omitting the closing boundary.
        """
        Tests the handling of an interrupted file upload by verifying that a temporary file is not left on the system after the upload is interrupted.
        """
        class MockedParser(Parser):
            def __iter__(self):
                """
                Custom iterator that yields items from the parent class, stopping when a file item is encountered.
                """
                for item in super().__iter__():
                    item_type, meta_data, field_stream = item
                    yield item_type, meta_data, field_stream
                    if item_type == FILE:
                        return

        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(b"a")
            temp_file.seek(0)
            with mock.patch(
                "django.http.multipartparser.Parser",
                MockedParser,
            ):
                response = self.client.post(
                    "/temp_file/upload_interrupted/",
                    {"file": temp_file},
                )
            temp_path = response.json()["temp_path"]
            self.assertIs(os.path.exists(temp_path), False)

    def test_upload_large_header_fields(self):
        """
        Tests uploading a file with large header fields to ensure the server can handle it without issue, verifying a successful response with the expected file contents.
        """
        payload = client.FakePayload(
            "\r\n".join(
                [
                    "--" + client.BOUNDARY,
                    'Content-Disposition: form-data; name="my_file"; '
                    'filename="test.txt"',
                    "Content-Type: text/plain",
                    "X-Long-Header: %s" % ("-" * 500),
                    "",
                    "file contents",
                    "--" + client.BOUNDARY + "--\r\n",
                ]
            ),
        )
        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/echo_content/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"my_file": "file contents"})

    def test_upload_header_fields_too_large(self):
        payload = client.FakePayload(
            "\r\n".join(
                [
                    "--" + client.BOUNDARY,
                    'Content-Disposition: form-data; name="my_file"; '
                    'filename="test.txt"',
                    "Content-Type: text/plain",
                    "X-Long-Header: %s" % ("-" * (MAX_TOTAL_HEADER_SIZE + 1)),
                    "",
                    "file contents",
                    "--" + client.BOUNDARY + "--\r\n",
                ]
            ),
        )
        r = {
            "CONTENT_LENGTH": len(payload),
            "CONTENT_TYPE": client.MULTIPART_CONTENT,
            "PATH_INFO": "/echo_content/",
            "REQUEST_METHOD": "POST",
            "wsgi.input": payload,
        }
        response = self.client.request(**r)
        self.assertEqual(response.status_code, 400)

    def test_fileupload_getlist(self):
        """
        Test that file upload handling returns the correct file count.

        Tests the '/getlist_count/' endpoint with multiple file uploads, 
        verifying that the response contains the expected file counts.
        """
        file = tempfile.NamedTemporaryFile
        with file() as file1, file() as file2, file() as file2a:
            file1.write(b"a" * (2**23))
            file1.seek(0)

            file2.write(b"a" * (2 * 2**18))
            file2.seek(0)

            file2a.write(b"a" * (5 * 2**20))
            file2a.seek(0)

            response = self.client.post(
                "/getlist_count/",
                {
                    "file1": file1,
                    "field1": "test",
                    "field2": "test3",
                    "field3": "test5",
                    "field4": "test6",
                    "field5": "test7",
                    "file2": (file2, file2a),
                },
            )
            got = response.json()
            self.assertEqual(got.get("file1"), 1)
            self.assertEqual(got.get("file2"), 2)

    def test_fileuploads_closed_at_request_end(self):
        """
        Tests that uploaded files are properly closed after the request has ended, ensuring resources are released and preventing potential file descriptor leaks.
        """
        file = tempfile.NamedTemporaryFile
        with file() as f1, file() as f2a, file() as f2b:
            response = self.client.post(
                "/fd_closing/t/",
                {
                    "file": f1,
                    "file2": (f2a, f2b),
                },
            )

        request = response.wsgi_request
        # The files were parsed.
        self.assertTrue(hasattr(request, "_files"))

        file = request._files["file"]
        self.assertTrue(file.closed)

        files = request._files.getlist("file2")
        self.assertTrue(files[0].closed)
        self.assertTrue(files[1].closed)

    def test_no_parsing_triggered_by_fd_closing(self):
        """
        Tests if the WSGI request doesn't have a `_files` attribute after the view handling the '/fd_closing/f/' URL has finished processing a request that includes a file and a faulty file descriptor. This ensures that file parsing is not triggered when a file descriptor is closed.
        """
        file = tempfile.NamedTemporaryFile
        with file() as f1, file() as f2a, file() as f2b:
            response = self.client.post(
                "/fd_closing/f/",
                {
                    "file": f1,
                    "file2": (f2a, f2b),
                },
            )

        request = response.wsgi_request
        # The fd closing logic doesn't trigger parsing of the stream
        self.assertFalse(hasattr(request, "_files"))

    def test_file_error_blocking(self):
        """

        Test that the server handles file upload errors without entering an infinite loop.

        Verifies that when an exception occurs during file upload, the server does not block
        and correctly handles subsequent requests, avoiding repeated exception handling
        that could cause an infinite loop.

        """

        class POSTAccessingHandler(client.ClientHandler):
            """A handler that'll access POST during an exception."""

            def handle_uncaught_exception(self, request, resolver, exc_info):
                ret = super().handle_uncaught_exception(request, resolver, exc_info)
                request.POST  # evaluate
                return ret

        # Maybe this is a little more complicated that it needs to be; but if
        # the django.test.client.FakePayload.read() implementation changes then
        # this test would fail.  So we need to know exactly what kind of error
        # it raises when there is an attempt to read more than the available bytes:
        try:
            client.FakePayload(b"a").read(2)
        except Exception as err:
            reference_error = err

        # install the custom handler that tries to access request.POST
        self.client.handler = POSTAccessingHandler()

        with open(__file__, "rb") as fp:
            post_data = {
                "name": "Ringo",
                "file_field": fp,
            }
            try:
                self.client.post("/upload_errors/", post_data)
            except reference_error.__class__ as err:
                self.assertNotEqual(
                    str(err),
                    str(reference_error),
                    "Caught a repeated exception that'll cause an infinite loop in "
                    "file uploads.",
                )
            except Exception as err:
                # CustomUploadError is the error that should have been raised
                self.assertEqual(err.__class__, uploadhandler.CustomUploadError)

    def test_filename_case_preservation(self):
        """
        Tests whether the storage backend preserves the case of filenames during file uploads.
        """
        # Synthesize the contents of a file upload with a mixed case filename
        # so we don't have to carry such a file in the Django tests source code
        # tree.
        vars = {"boundary": "oUrBoUnDaRyStRiNg"}
        post_data = [
            "--%(boundary)s",
            'Content-Disposition: form-data; name="file_field"; '
            'filename="MiXeD_cAsE.txt"',
            "Content-Type: application/octet-stream",
            "",
            "file contents\n",
            "--%(boundary)s--\r\n",
        ]
        response = self.client.post(
            "/filename_case/",
            "\r\n".join(post_data) % vars,
            "multipart/form-data; boundary=%(boundary)s" % vars,
        )
        self.assertEqual(response.status_code, 200)
        id = int(response.content)
        obj = FileModel.objects.get(pk=id)
        # The name of the file uploaded and the file stored in the server-side
        # shouldn't differ.
        self.assertEqual(os.path.basename(obj.testfile.path), "MiXeD_cAsE.txt")

    def test_filename_traversal_upload(self):
        """
        Tests the upload functionality to prevent directory traversal attacks through the filename parameter.

        The test checks if a file can be uploaded with a filename that contains traversal characters ('..'), 
        and verifies that the file is uploaded to the correct directory and the traversal attempt is prevented.
        """
        os.makedirs(UPLOAD_TO, exist_ok=True)
        tests = [
            "..&#x2F;test.txt",
            "..&sol;test.txt",
        ]
        for file_name in tests:
            with self.subTest(file_name=file_name):
                payload = client.FakePayload()
                payload.write(
                    "\r\n".join(
                        [
                            "--" + client.BOUNDARY,
                            'Content-Disposition: form-data; name="my_file"; '
                            'filename="%s";' % file_name,
                            "Content-Type: text/plain",
                            "",
                            "file contents.\r\n",
                            "\r\n--" + client.BOUNDARY + "--\r\n",
                        ]
                    ),
                )
                r = {
                    "CONTENT_LENGTH": len(payload),
                    "CONTENT_TYPE": client.MULTIPART_CONTENT,
                    "PATH_INFO": "/upload_traversal/",
                    "REQUEST_METHOD": "POST",
                    "wsgi.input": payload,
                }
                response = self.client.request(**r)
                result = response.json()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(result["file_name"], "test.txt")
                self.assertIs(
                    os.path.exists(os.path.join(MEDIA_ROOT, "test.txt")),
                    False,
                )
                self.assertIs(
                    os.path.exists(os.path.join(UPLOAD_TO, "test.txt")),
                    True,
                )


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DirectoryCreationTests(SimpleTestCase):
    """
    Tests for error handling during directory creation
    via _save_FIELD_file (ticket #6450)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.makedirs(MEDIA_ROOT, exist_ok=True)
        cls.addClassCleanup(shutil.rmtree, MEDIA_ROOT)

    def setUp(self):
        self.obj = FileModel()

    @unittest.skipIf(
        sys.platform == "win32", "Python on Windows doesn't have working os.chmod()."
    )
    @override_settings(
        STORAGES={
            DEFAULT_STORAGE_ALIAS: {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            }
        }
    )
    def test_readonly_root(self):
        """
        Tests whether permission errors are properly propagated when the media root directory is set to read-only, ensuring that they are not silently ignored by the application.
        """
        os.chmod(MEDIA_ROOT, 0o500)
        self.addCleanup(os.chmod, MEDIA_ROOT, 0o700)
        with self.assertRaises(PermissionError):
            self.obj.testfile.save(
                "foo.txt", SimpleUploadedFile("foo.txt", b"x"), save=False
            )

    def test_not_a_directory(self):
        """
        Tests that attempting to save a file to a path where a non-directory file already exists raises a FileExistsError.
        """
        default_storage.delete(UPLOAD_TO)
        # Create a file with the upload directory name
        with SimpleUploadedFile(UPLOAD_TO, b"x") as file:
            default_storage.save(UPLOAD_FOLDER, file)
        self.addCleanup(default_storage.delete, UPLOAD_TO)
        msg = "%s exists and is not a directory." % UPLOAD_TO
        with self.assertRaisesMessage(FileExistsError, msg):
            with SimpleUploadedFile("foo.txt", b"x") as file:
                self.obj.testfile.save("foo.txt", file, save=False)


class MultiParserTests(SimpleTestCase):
    def test_empty_upload_handlers(self):
        # We're not actually parsing here; just checking if the parser properly
        # instantiates with empty upload handlers.
        MultiPartParser(
            {
                "CONTENT_TYPE": "multipart/form-data; boundary=_foo",
                "CONTENT_LENGTH": "1",
            },
            StringIO("x"),
            [],
            "utf-8",
        )

    def test_invalid_content_type(self):
        with self.assertRaisesMessage(
            MultiPartParserError, "Invalid Content-Type: text/plain"
        ):
            MultiPartParser(
                {
                    "CONTENT_TYPE": "text/plain",
                    "CONTENT_LENGTH": "1",
                },
                StringIO("x"),
                [],
                "utf-8",
            )

    def test_negative_content_length(self):
        with self.assertRaisesMessage(
            MultiPartParserError, "Invalid content length: -1"
        ):
            MultiPartParser(
                {
                    "CONTENT_TYPE": "multipart/form-data; boundary=_foo",
                    "CONTENT_LENGTH": -1,
                },
                StringIO("x"),
                [],
                "utf-8",
            )

    def test_bad_type_content_length(self):
        multipart_parser = MultiPartParser(
            {
                "CONTENT_TYPE": "multipart/form-data; boundary=_foo",
                "CONTENT_LENGTH": "a",
            },
            StringIO("x"),
            [],
            "utf-8",
        )
        self.assertEqual(multipart_parser._content_length, 0)

    def test_sanitize_file_name(self):
        parser = MultiPartParser(
            {
                "CONTENT_TYPE": "multipart/form-data; boundary=_foo",
                "CONTENT_LENGTH": "1",
            },
            StringIO("x"),
            [],
            "utf-8",
        )
        for file_name in CANDIDATE_TRAVERSAL_FILE_NAMES:
            with self.subTest(file_name=file_name):
                self.assertEqual(parser.sanitize_file_name(file_name), "hax0rd.txt")

    def test_sanitize_invalid_file_name(self):
        parser = MultiPartParser(
            {
                "CONTENT_TYPE": "multipart/form-data; boundary=_foo",
                "CONTENT_LENGTH": "1",
            },
            StringIO("x"),
            [],
            "utf-8",
        )
        for file_name in CANDIDATE_INVALID_FILE_NAMES:
            with self.subTest(file_name=file_name):
                self.assertIsNone(parser.sanitize_file_name(file_name))
