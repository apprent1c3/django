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
        """
        Sets up the test class by creating the media root directory if it does not exist.

         The directory is created with the exist_ok flag set to True, meaning that if the directory already exists, no exception is raised.

         Additionally, a class cleanup is added to remove the media root directory after all tests in the class have finished running, ensuring a clean environment for subsequent tests.
        """
        super().setUpClass()
        os.makedirs(MEDIA_ROOT, exist_ok=True)
        cls.addClassCleanup(shutil.rmtree, MEDIA_ROOT)

    def test_upload_name_is_validated(self):
        """
        Tests the validation of uploaded file names to prevent suspicious operations.

        Checks that UploadedFile raises a SuspiciousFileOperation exception when 
        given file names that are likely to be used in unauthorized file access 
        attempts, such as names that resolve to parent directory ('..') or the 
        current directory ('.').

        The test includes platform-specific file name examples for Windows and 
        other operating systems to ensure validation works correctly across 
        different platforms.
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
        """
        Tests a simple file upload to the '/upload/' endpoint.

        Checks that a file can be successfully uploaded by sending a POST request
        to the specified endpoint with a file attached to the 'file_field' form field.
        The test verifies that the server responds with a 200 status code, indicating
        a successful upload.
        """
        with open(__file__, "rb") as fp:
            post_data = {
                "name": "Ringo",
                "file_field": fp,
            }
            response = self.client.post("/upload/", post_data)
        self.assertEqual(response.status_code, 200)

    def test_large_upload(self):
        """
        Tests the successful upload of large files through the '/verify/' endpoint.

        This test creates two temporary files of different sizes (2MB and 10MB), adds them to a POST request
        along with a name field, calculates the SHA-1 hash of each file, and sends the request to the server.
        The function then asserts that the server responds with a status code of 200, indicating a successful upload.

        The purpose of this test is to ensure that the server can handle large file uploads without errors or
        timeouts, and that the file hashing functionality works correctly for files of various sizes.
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

        Tests the upload of a file encoded in base64 via a multipart form request.

        This method sends a POST request to the /echo_content/ endpoint with a base64 encoded file in the request body.
        It then verifies that the server correctly decodes the file and returns its original content.

        The test can be customized to use different encoding methods by passing an alternative encoding function via the `encode` parameter.

        Parameters
        ----------
        content : str
            The content of the file to be uploaded.
        encode : function
            The encoding function to use for the file content (defaults to base64.b64encode).

        Returns
        -------
        None

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
        Tests the handling of an invalid base64 encoded file upload.

        This test case simulates a POST request with a multipart/form-data payload containing
        a file with a base64 content-transfer-encoding header. The file contents are intentionally
        malformed, containing non-base64 characters, to verify that the server correctly handles
        such errors. The response from the server is then validated to ensure that it returns an
        empty file, indicating that the invalid upload was rejected.

        Args: None

        Returns: None

        Raises: AssertionError if the server response does not match the expected result.
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

        Tests the handling of a file with a Unicode name.

        This test case creates a temporary file with a Unicode name, writes data to it, and then submits it to the server via a POST request.
        The test verifies that the server responds with a successful status code (200), indicating that the file was handled correctly.

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
        Receiving file upload when filename is encoded with RFC 2231.
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
        Receiving file upload when filename is encoded with RFC 2231.
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

        Tests handling of a Unicode filename with double quotes in the name according to RFC 2231.

        This test sends a POST request with a multipart/form-data payload containing a file 
        with a Unicode name that includes double quotes. It verifies that the server can 
        parse the filename correctly and returns a successful response (200 status code).

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
        Receiving file upload when filename is blank (before and after
        sanitization) should be okay.
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

        Tests the handling of non-printable characters in file names during a multipart form-data request.

        This test verifies that the server correctly processes a file with a name containing non-printable characters,
        such as null bytes and newline characters, and that the received file name is sanitized to remove these characters.

        The expected outcome is that the server receives the file and returns a response with the sanitized file name.

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
        """Uploaded file names should be sanitized before ever reaching the view."""
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
        """File names over 256 characters (dangerous on some platforms) get fixed up."""
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

        Test the functionality of handling different types of file content in a POST request.

        This test creates temporary files with and without content types, as well as in-memory strings and binary data.
        It then sends these files and data to a server endpoint using a POST request and verifies that the server
        correctly receives and returns the content of each file and data stream.

        The test checks for the following scenarios:
        - A file without a content type
        - A file with a content type (in this case, 'text/plain')
        - A string sent as a file-like object
        - Binary data sent as a file-like object

        The test passes if the server correctly echoes back the content of each file and data stream.

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
        """Uploaded files may have content type parameters available."""
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
        If passed an incomplete multipart message, MultiPartParser does not
        attempt to read beyond the end of the stream, and simply will handle
        the part that can be parsed gracefully.
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
        Tests the functionality of stopping an upload of a temporary file.

        This test case simulates an upload of a temporary file and verifies that the 
        file is properly removed when the upload is stopped. It checks if the temporary 
        file path returned in the response no longer corresponds to an existing file on 
        the file system after the upload has been stopped. 

        The test ensures that the server correctly handles the stop upload request and 
        removes the temporary file as expected.
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
        Tests the handling of interrupted file uploads by verifying that a temporary file created during the upload process is properly deleted when the upload is interrupted.

        The test simulates a file upload with an interrupted request, and checks that the temporary file is not left behind on the server. It ensures that the system correctly cleans up after an interrupted upload operation.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the temporary file created during the interrupted upload still exists after the upload is completed.

        This test case covers the scenario where a file upload is interrupted before completion, and verifies that the system's temporary file handling mechanism behaves as expected in such cases.
        """
        class MockedParser(Parser):
            def __iter__(self):
                """
                .. method:: __iter__()

                   Returns an iterator over the items in the object, yielding a tuple for each item containing its type, meta data, and field stream. The iteration stops when a file type item is encountered.
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
        Tests the upload functionality when dealing with large header fields.

        This test case simulates a POST request with a multipart/form-data payload containing a file,
        where one of the header fields has a notably large value. It verifies that the request is
        successfully processed and the response contains the expected data.

        The test checks for a status code of 200 and ensures that the JSON response matches the
        expected output, confirming that the large header field does not interfere with the
        upload process or the parsing of the request contents.
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
        """
        Tests that uploading a file with header fields that exceed the maximum allowed size results in a bad request response (400 status code).

        This test simulates an HTTP POST request with a multipart/form-data payload containing a file, where one of the header fields ('X-Long-Header') has a value that exceeds the maximum total header size.

        The test verifies that the server correctly rejects the request and returns a 400 status code, indicating a bad request.

        """
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

        Tests whether file uploads are properly closed at the end of a request.

        This test case simulates a file upload request with multiple files and 
        verifies that all uploaded files are closed after the request has been processed.
        It checks the request object's attributes to ensure that the uploaded files 
        are no longer open, preventing potential resource leaks.

        The test covers the following scenarios:

        * Single file upload
        * Multiple file upload with the same name

        By verifying that all uploaded files are closed, this test ensures that 
        the application behaves correctly and does not waste system resources.

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
        The server should not block when there are upload errors (bug #8622).
        This can happen if something -- i.e. an exception handler -- tries to
        access POST while handling an error in parsing POST. This shouldn't
        cause an infinite loop!
        """

        class POSTAccessingHandler(client.ClientHandler):
            """A handler that'll access POST during an exception."""

            def handle_uncaught_exception(self, request, resolver, exc_info):
                """
                Handles uncaught exceptions that occur during the resolution of a request.

                This method is called when an exception is raised during the processing of a request.
                It allows for additional handling and inspection of the exception, while also permitting
                the base class to perform its standard exception handling.

                The method provides access to the original request, the resolver that was being used,
                and information about the exception that was raised, including its type, value, and traceback.

                Parameters
                ----------
                request : object
                    The request that was being processed when the exception occurred.
                resolver : object
                    The resolver that was being used to process the request.
                exc_info : tuple
                    A tuple containing information about the exception, including its type, value, and traceback.

                Returns
                -------
                object
                    The result of the base class's exception handling, which may or may not include additional
                    information or modified behavior based on the specifics of the exception and request.

                """
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
        The storage backend shouldn't mess with the case of the filenames
        uploaded.
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
        Tests the filename traversal vulnerability in file uploads.

        This test ensures that the server correctly handles filenames with 
        directory traversal characters ('..' and '/\' or '\'') and prevents 
        uploads from being written outside of the intended upload directory.

        The test sends a POST request with a multipart/form-data payload 
        containing a file with a specially crafted filename, and checks that 
        the server responds with a 200 status code and writes the file to the 
        correct location within the upload directory, without allowing the 
        file to be written to an arbitrary location on the server's filesystem.

        The test covers two types of directory traversal attempts: using 
        '..' with a forward slash ('/'), and using '..' with a backslash 
        ('\' or '\\').
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
        """

        Sets up the class by creating a directory for media storage and schedules its removal after testing.

        This method is used as a class-level setup, ensuring that the required media directory exists
        before running any tests. After all tests have been executed, the directory and its contents
        will be deleted to maintain a clean environment.

        """
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
        """Permission errors are not swallowed"""
        os.chmod(MEDIA_ROOT, 0o500)
        self.addCleanup(os.chmod, MEDIA_ROOT, 0o700)
        with self.assertRaises(PermissionError):
            self.obj.testfile.save(
                "foo.txt", SimpleUploadedFile("foo.txt", b"x"), save=False
            )

    def test_not_a_directory(self):
        """
        Tests that a FileExistsError is raised when attempting to save a file to 
        a location that exists but is not a directory.

        Verifies that the testfile instance correctly handles cases where the 
        destination is occupied by a non-directory file. The test ensures the 
        expected error message is provided, indicating the path that exists and 
        is not a directory. This check is crucial for maintaining data integrity 
        and providing informative error messages in case of conflicts during file 
        saving operations.
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
        """

        Tests that a MultiPartParserError is raised when the content type is invalid.

        This test case verifies that the MultiPartParser correctly handles requests with
        an invalid Content-Type header. In this scenario, a 'text/plain' content type is
        provided, which is not supported by the MultiPartParser. The test checks that
        the expected error message 'Invalid Content-Type: text/plain' is raised.

        :raises: MultiPartParserError

        """
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
        """

        Verify that a MultiPartParserError is raised when the content length is negative.

        This test case checks that the parser correctly identifies and raises an error
        when the content length is set to an invalid value, specifically a negative number.
        The test ensures that the parser's error handling behaves as expected in this scenario.

        """
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
        """
        Tests that the MultiPartParser correctly handles a request with a malformed CONTENT_LENGTH header, ensuring that the content length is set to 0 when the provided value cannot be converted to an integer.
        """
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
