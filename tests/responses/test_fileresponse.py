import io
import itertools
import os
import sys
import tempfile
from unittest import skipIf

from django.core.files.base import ContentFile
from django.http import FileResponse
from django.test import SimpleTestCase


class UnseekableBytesIO(io.BytesIO):
    def seekable(self):
        return False


class FileResponseTests(SimpleTestCase):
    def test_content_length_file(self):
        """

        Test that the Content-Length header of a FileResponse is correctly set to the size of the file.

        This test case verifies that when a FileResponse is created for a given file, the Content-Length
        header in the response is equal to the actual size of the file in bytes.

        """
        response = FileResponse(open(__file__, "rb"))
        response.close()
        self.assertEqual(
            response.headers["Content-Length"], str(os.path.getsize(__file__))
        )

    def test_content_length_buffer(self):
        """

        Tests that the Content-Length header is correctly calculated for a FileResponse.

        This test case verifies that when a FileResponse is created with a binary content,
        the 'Content-Length' header in the response is set to the correct value, which is
        the size of the content in bytes.

        """
        response = FileResponse(io.BytesIO(b"binary content"))
        self.assertEqual(response.headers["Content-Length"], "14")

    def test_content_length_nonzero_starting_position_file(self):
        """
        Tests that the Content-Length header is correctly calculated when the starting position of a file is non-zero. 
        This test case covers the scenario where a file is being served from a non-zero offset, verifying that the response includes an accurate Content-Length header based on the remaining size of the file from the specified starting position.
        """
        file = open(__file__, "rb")
        file.seek(10)
        response = FileResponse(file)
        response.close()
        self.assertEqual(
            response.headers["Content-Length"], str(os.path.getsize(__file__) - 10)
        )

    def test_content_length_nonzero_starting_position_buffer(self):
        test_tuples = (
            ("BytesIO", io.BytesIO),
            ("UnseekableBytesIO", UnseekableBytesIO),
        )
        for buffer_class_name, BufferClass in test_tuples:
            with self.subTest(buffer_class_name=buffer_class_name):
                buffer = BufferClass(b"binary content")
                buffer.seek(10)
                response = FileResponse(buffer)
                self.assertEqual(response.headers["Content-Length"], "4")

    def test_content_length_nonzero_starting_position_file_seekable_no_tell(self):
        """

        Tests that the Content-Length header is set correctly when a file is sent from a non-zero starting position.
        The test uses a seekable file and checks that the Content-Length header reflects the remaining size of the file.

        """
        class TestFile:
            def __init__(self, path, *args, **kwargs):
                self._file = open(path, *args, **kwargs)

            def read(self, n_bytes=-1):
                return self._file.read(n_bytes)

            def seek(self, offset, whence=io.SEEK_SET):
                return self._file.seek(offset, whence)

            def seekable(self):
                return True

            @property
            def name(self):
                return self._file.name

            def close(self):
                """

                Closes the associated file, releasing any system resources.

                This method checks if a file is currently open and, if so, properly closes it to
                prevent resource leaks. After closure, the file reference is reset to indicate
                that the file is no longer available for operations.

                """
                if self._file:
                    self._file.close()
                    self._file = None

            def __enter__(self):
                return self

            def __exit__(self, e_type, e_val, e_tb):
                self.close()

        file = TestFile(__file__, "rb")
        file.seek(10)
        response = FileResponse(file)
        response.close()
        self.assertEqual(
            response.headers["Content-Length"], str(os.path.getsize(__file__) - 10)
        )

    def test_content_type_file(self):
        """
        Tests that the Content-Type header of a FileResponse object is correctly set when serving a Python file.

        The function verifies that the Content-Type header is either 'text/x-python' or 'text/plain', 
        which are standard MIME types for Python files, after the response has been properly closed.
        """
        response = FileResponse(open(__file__, "rb"))
        response.close()
        self.assertIn(response.headers["Content-Type"], ["text/x-python", "text/plain"])

    def test_content_type_buffer(self):
        response = FileResponse(io.BytesIO(b"binary content"))
        self.assertEqual(response.headers["Content-Type"], "application/octet-stream")

    def test_content_type_buffer_explicit(self):
        """
        Tests that the content type is correctly set in the response headers when 
        explicitly provided to the FileResponse object. 

        This test case verifies the expected behavior of the content type buffer 
        when a specific content type is explicitly defined. It ensures that the 
        response headers accurately reflect the provided content type.

        :raises AssertionError: If the response headers do not contain the expected 
                                 content type.
        """
        response = FileResponse(
            io.BytesIO(b"binary content"), content_type="video/webm"
        )
        self.assertEqual(response.headers["Content-Type"], "video/webm")

    def test_content_type_buffer_explicit_default(self):
        response = FileResponse(
            io.BytesIO(b"binary content"), content_type="text/html; charset=utf-8"
        )
        self.assertEqual(response.headers["Content-Type"], "text/html; charset=utf-8")

    def test_content_type_buffer_named(self):
        test_tuples = (
            (__file__, ["text/x-python", "text/plain"]),
            (__file__ + "nosuchfile", ["application/octet-stream"]),
            ("test_fileresponse.py", ["text/x-python", "text/plain"]),
            ("test_fileresponse.pynosuchfile", ["application/octet-stream"]),
        )
        for filename, content_types in test_tuples:
            with self.subTest(filename=filename):
                buffer = io.BytesIO(b"binary content")
                buffer.name = filename
                response = FileResponse(buffer)
                self.assertIn(response.headers["Content-Type"], content_types)

    def test_content_disposition_file(self):
        filenames = (
            ("", "test_fileresponse.py"),
            ("custom_name.py", "custom_name.py"),
        )
        dispositions = (
            (False, "inline"),
            (True, "attachment"),
        )
        for (filename, header_filename), (
            as_attachment,
            header_disposition,
        ) in itertools.product(filenames, dispositions):
            with self.subTest(filename=filename, disposition=header_disposition):
                response = FileResponse(
                    open(__file__, "rb"), filename=filename, as_attachment=as_attachment
                )
                response.close()
                self.assertEqual(
                    response.headers["Content-Disposition"],
                    '%s; filename="%s"' % (header_disposition, header_filename),
                )

    def test_content_disposition_escaping(self):
        # fmt: off
        """
        Tests the escaping of special characters in the Content-Disposition header of a FileResponse.

        Verifies that the filename is correctly escaped according to the Content-Disposition specification
        to prevent potential security vulnerabilities. The test checks different scenarios, including 
        filenames with special characters and platform-specific escaping requirements.

        The test covers various test cases with different filename patterns and verifies that the 
        Content-Disposition header of the response contains the expected escaped filename.

        """
        tests = [
            (
                'multi-part-one";\" dummy".txt',
                r"multi-part-one\";\" dummy\".txt"
            ),
        ]
        # fmt: on
        # Non-escape sequence backslashes are path segments on Windows, and are
        # eliminated by an os.path.basename() check in FileResponse.
        if sys.platform != "win32":
            # fmt: off
            tests += [
                (
                    'multi-part-one\\";\" dummy".txt',
                    r"multi-part-one\\\";\" dummy\".txt"
                ),
                (
                    'multi-part-one\\";\\\" dummy".txt',
                    r"multi-part-one\\\";\\\" dummy\".txt"
                )
            ]
            # fmt: on
        for filename, escaped in tests:
            with self.subTest(filename=filename, escaped=escaped):
                response = FileResponse(
                    io.BytesIO(b"binary content"), filename=filename, as_attachment=True
                )
                response.close()
                self.assertEqual(
                    response.headers["Content-Disposition"],
                    f'attachment; filename="{escaped}"',
                )

    def test_content_disposition_buffer(self):
        """
        Tests the Content-Disposition header is not present in the response when 
        a binary buffer is served without specifying a filename. This ensures 
        the correct handling of binary content in the FileResponse class, 
        preventing unnecessary headers from being sent to the client.
        """
        response = FileResponse(io.BytesIO(b"binary content"))
        self.assertFalse(response.has_header("Content-Disposition"))

    def test_content_disposition_buffer_attachment(self):
        response = FileResponse(io.BytesIO(b"binary content"), as_attachment=True)
        self.assertEqual(response.headers["Content-Disposition"], "attachment")

    def test_content_disposition_buffer_explicit_filename(self):
        """
        Tests the Content-Disposition header in the response for file downloads.

        This function verifies that the Content-Disposition header is correctly set 
        when generating a response for a file download, with and without specifying 
        the file as an attachment. It checks that the filename specified in the 
        response matches the filename provided to the FileResponse constructor.

        The test covers two scenarios: when the file is sent inline and when it is 
        sent as an attachment, ensuring that the Content-Disposition header is 
        formatted correctly in both cases.
        """
        dispositions = (
            (False, "inline"),
            (True, "attachment"),
        )
        for as_attachment, header_disposition in dispositions:
            response = FileResponse(
                io.BytesIO(b"binary content"),
                as_attachment=as_attachment,
                filename="custom_name.py",
            )
            self.assertEqual(
                response.headers["Content-Disposition"],
                '%s; filename="custom_name.py"' % header_disposition,
            )

    def test_response_buffer(self):
        response = FileResponse(io.BytesIO(b"binary content"))
        self.assertEqual(list(response), [b"binary content"])

    def test_response_nonzero_starting_position(self):
        test_tuples = (
            ("BytesIO", io.BytesIO),
            ("UnseekableBytesIO", UnseekableBytesIO),
        )
        for buffer_class_name, BufferClass in test_tuples:
            with self.subTest(buffer_class_name=buffer_class_name):
                buffer = BufferClass(b"binary content")
                buffer.seek(10)
                response = FileResponse(buffer)
                self.assertEqual(list(response), [b"tent"])

    def test_buffer_explicit_absolute_filename(self):
        """
        Headers are set correctly with a buffer when an absolute filename is
        provided.
        """
        response = FileResponse(io.BytesIO(b"binary content"), filename=__file__)
        self.assertEqual(response.headers["Content-Length"], "14")
        self.assertEqual(
            response.headers["Content-Disposition"],
            'inline; filename="test_fileresponse.py"',
        )

    @skipIf(sys.platform == "win32", "Named pipes are Unix-only.")
    def test_file_from_named_pipe_response(self):
        """
        Tests that a FileResponse created from a named pipe returns the correct content.

        This test verifies that the FileResponse can handle reading from a named pipe and
        that the Content-Length header is not included in the response, as the length of
        the pipe's content is unknown.

        The test case creates a temporary named pipe, writes binary content to it, and
        then creates a FileResponse object from the pipe. It checks that the response
        content matches the written binary content and that the response does not include
        a Content-Length header.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            pipe_file = os.path.join(temp_dir, "named_pipe")
            os.mkfifo(pipe_file)
            pipe_for_read = os.open(pipe_file, os.O_RDONLY | os.O_NONBLOCK)
            with open(pipe_file, "wb") as pipe_for_write:
                pipe_for_write.write(b"binary content")

            response = FileResponse(os.fdopen(pipe_for_read, mode="rb"))
            response_content = list(response)
            response.close()
            self.assertEqual(response_content, [b"binary content"])
            self.assertFalse(response.has_header("Content-Length"))

    def test_compressed_response(self):
        """
        If compressed responses are served with the uncompressed Content-Type
        and a compression Content-Encoding, browsers might automatically
        uncompress the file, which is most probably not wanted.
        """
        test_tuples = (
            (".tar.gz", "application/gzip"),
            (".tar.br", "application/x-brotli"),
            (".tar.bz2", "application/x-bzip"),
            (".tar.xz", "application/x-xz"),
            (".tar.Z", "application/x-compress"),
        )
        for extension, mimetype in test_tuples:
            with self.subTest(ext=extension):
                with tempfile.NamedTemporaryFile(suffix=extension) as tmp:
                    response = FileResponse(tmp)
                self.assertEqual(response.headers["Content-Type"], mimetype)
                self.assertFalse(response.has_header("Content-Encoding"))

    def test_unicode_attachment(self):
        response = FileResponse(
            ContentFile(b"binary content", name="祝您平安.odt"),
            as_attachment=True,
            content_type="application/vnd.oasis.opendocument.text",
        )
        self.assertEqual(
            response.headers["Content-Type"],
            "application/vnd.oasis.opendocument.text",
        )
        self.assertEqual(
            response.headers["Content-Disposition"],
            "attachment; filename*=utf-8''%E7%A5%9D%E6%82%A8%E5%B9%B3%E5%AE%89.odt",
        )

    def test_repr(self):
        """
        Tests the representation of a FileResponse object.

        Verifies that the string representation of a FileResponse instance is correctly formatted, 
        including the status code and content type. The representation should be in the format 
        '<FileResponse status_code=**statusCode**, \"**contentType**\">'.

        This test ensures that the repr function of the FileResponse class provides a clear and 
        informative string representation of the object, making it easier to debug and understand 
        the object's state.
        """
        response = FileResponse(io.BytesIO(b"binary content"))
        self.assertEqual(
            repr(response),
            '<FileResponse status_code=200, "application/octet-stream">',
        )
