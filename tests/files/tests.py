import errno
import gzip
import os
import struct
import tempfile
import unittest
from io import BytesIO, StringIO, TextIOWrapper
from pathlib import Path
from unittest import mock

from django.core.files import File, locks
from django.core.files.base import ContentFile
from django.core.files.move import file_move_safe
from django.core.files.temp import NamedTemporaryFile
from django.core.files.uploadedfile import (
    InMemoryUploadedFile,
    SimpleUploadedFile,
    TemporaryUploadedFile,
    UploadedFile,
)
from django.test import override_settings

try:
    from PIL import Image, features

    HAS_WEBP = features.check("webp")
except ImportError:
    Image = None
    HAS_WEBP = False
else:
    from django.core.files import images


class FileTests(unittest.TestCase):
    def test_unicode_uploadedfile_name(self):
        """
        Tests that the representation of an UploadedFile instance with a Unicode filename returns a string.

        This test case ensures that the repr() function can handle uploaded files with names containing non-ASCII characters, such as accents and non-Latin scripts, and that the result is a valid string. This is important for debugging and logging purposes, where a meaningful string representation of the uploaded file is required.
        """
        uf = UploadedFile(name="¿Cómo?", content_type="text")
        self.assertIs(type(repr(uf)), str)

    def test_unicode_file_name(self):
        f = File(None, "djángö")
        self.assertIs(type(repr(f)), str)

    def test_context_manager(self):
        orig_file = tempfile.TemporaryFile()
        base_file = File(orig_file)
        with base_file as f:
            self.assertIs(base_file, f)
            self.assertFalse(f.closed)
        self.assertTrue(f.closed)
        self.assertTrue(orig_file.closed)

    def test_open_resets_opened_file_to_start_and_returns_context_manager(self):
        file = File(BytesIO(b"content"))
        file.read()
        with file.open() as f:
            self.assertEqual(f.read(), b"content")

    def test_open_reopens_closed_file_and_returns_context_manager(self):
        """
        Tests that the open method of a File instance can reopen a previously closed file.

        This method verifies that the open method returns a context manager that yields a file object,
        and that the file object is not closed after the open method is called, even if the file was previously closed.

        The test involves creating a temporary file, closing it, and then reopening it using the open method.
        The reopened file is checked to ensure it is not closed, demonstrating the correct behavior of the open method.

        This test is important to ensure that the File class behaves correctly when working with files that may need to be reopened after being closed.
        """
        temporary_file = tempfile.NamedTemporaryFile(delete=False)
        file = File(temporary_file)
        try:
            file.close()
            with file.open() as f:
                self.assertFalse(f.closed)
        finally:
            # remove temporary file
            os.unlink(file.name)

    def test_namedtemporaryfile_closes(self):
        """
        The symbol django.core.files.NamedTemporaryFile is assigned as
        a different class on different operating systems. In
        any case, the result should minimally mock some of the API of
        tempfile.NamedTemporaryFile from the Python standard library.
        """
        tempfile = NamedTemporaryFile()
        self.assertTrue(hasattr(tempfile, "closed"))
        self.assertFalse(tempfile.closed)

        tempfile.close()
        self.assertTrue(tempfile.closed)

    def test_file_mode(self):
        # Should not set mode to None if it is not present.
        # See #14681, stdlib gzip module crashes if mode is set to None
        file = SimpleUploadedFile("mode_test.txt", b"content")
        self.assertFalse(hasattr(file, "mode"))
        gzip.GzipFile(fileobj=file)

    def test_file_iteration(self):
        """
        File objects should yield lines when iterated over.
        Refs #22107.
        """
        file = File(BytesIO(b"one\ntwo\nthree"))
        self.assertEqual(list(file), [b"one\n", b"two\n", b"three"])

    def test_file_iteration_windows_newlines(self):
        """
        #8149 - File objects with \r\n line endings should yield lines
        when iterated over.
        """
        f = File(BytesIO(b"one\r\ntwo\r\nthree"))
        self.assertEqual(list(f), [b"one\r\n", b"two\r\n", b"three"])

    def test_file_iteration_mac_newlines(self):
        """
        #8149 - File objects with \r line endings should yield lines
        when iterated over.
        """
        f = File(BytesIO(b"one\rtwo\rthree"))
        self.assertEqual(list(f), [b"one\r", b"two\r", b"three"])

    def test_file_iteration_mixed_newlines(self):
        f = File(BytesIO(b"one\rtwo\nthree\r\nfour"))
        self.assertEqual(list(f), [b"one\r", b"two\n", b"three\r\n", b"four"])

    def test_file_iteration_with_unix_newline_at_chunk_boundary(self):
        """
        Tests that a file can be iterated over in chunks when a Unix newline is present at a chunk boundary.

        The function verifies that the file is correctly split into chunks, even when a newline character falls at the end of a chunk, ensuring that each chunk contains a complete line of text.

        This test case is specific to the scenario where the file uses Unix-style newlines ('\n') and the chunk size is set to a value that causes a newline to be at the boundary between two chunks. The test checks that the resulting chunks are correctly generated and match the expected output. 
        """
        f = File(BytesIO(b"one\ntwo\nthree"))
        # Set chunk size to create a boundary after \n:
        # b'one\n...
        #        ^
        f.DEFAULT_CHUNK_SIZE = 4
        self.assertEqual(list(f), [b"one\n", b"two\n", b"three"])

    def test_file_iteration_with_windows_newline_at_chunk_boundary(self):
        f = File(BytesIO(b"one\r\ntwo\r\nthree"))
        # Set chunk size to create a boundary between \r and \n:
        # b'one\r\n...
        #        ^
        f.DEFAULT_CHUNK_SIZE = 4
        self.assertEqual(list(f), [b"one\r\n", b"two\r\n", b"three"])

    def test_file_iteration_with_mac_newline_at_chunk_boundary(self):
        """
        Tests file iteration with a Mac newline character (\\r) positioned at a chunk boundary, 
         ensuring that the file is split into chunks correctly and that all data is yielded. 
         This test case verifies the file iteration functionality in the presence of Mac newlines 
         at chunk boundaries, confirming that the resulting chunks are as expected.
        """
        f = File(BytesIO(b"one\rtwo\rthree"))
        # Set chunk size to create a boundary after \r:
        # b'one\r...
        #        ^
        f.DEFAULT_CHUNK_SIZE = 4
        self.assertEqual(list(f), [b"one\r", b"two\r", b"three"])

    def test_file_iteration_with_text(self):
        f = File(StringIO("one\ntwo\nthree"))
        self.assertEqual(list(f), ["one\n", "two\n", "three"])

    def test_readable(self):
        """
        Test whether a file object is readable within its context and not readable after it's closed.

        Checks if the file object returns True when its readability is queried while the file is open, and False after the context in which the file was opened has expired. This test verifies the expected behavior of file objects in regards to their lifecycle and readability status.
        """
        with (
            tempfile.TemporaryFile() as temp,
            File(temp, name="something.txt") as test_file,
        ):
            self.assertTrue(test_file.readable())
        self.assertFalse(test_file.readable())

    def test_writable(self):
        """
        Tests the writable status of a File object.

        Verifies that a File object created from a writable temporary file is indeed 
        writable, but becomes unwritable after the file is closed. Also checks that a 
        File object created from a read-only binary temporary file is not writable.

        This test ensures the correctness of the writable property of the File object 
        in different scenarios, such as when the underlying file is open or closed, 
        and when it is opened in read-only mode.
        """
        with (
            tempfile.TemporaryFile() as temp,
            File(temp, name="something.txt") as test_file,
        ):
            self.assertTrue(test_file.writable())
        self.assertFalse(test_file.writable())
        with (
            tempfile.TemporaryFile("rb") as temp,
            File(temp, name="something.txt") as test_file,
        ):
            self.assertFalse(test_file.writable())

    def test_seekable(self):
        """
        Checks the behavior of the seekable method in a File object.

        This test case verifies that the seekable method returns True when a File object is open and associated with a seekable file,
        and False when the File object is closed.

        The test uses a temporary file to create a File object and checks its seekability in both open and closed states
        """
        with (
            tempfile.TemporaryFile() as temp,
            File(temp, name="something.txt") as test_file,
        ):
            self.assertTrue(test_file.seekable())
        self.assertFalse(test_file.seekable())

    def test_io_wrapper(self):
        """

        Test the functionality of a text I/O wrapper.

        This test ensures that the TextIOWrapper class correctly reads and writes text data
        to and from an underlying file object, handling encoding and newline characters as
        expected. It verifies that the wrapper can write data, read back the data, and then
        detach from the underlying file object, leaving the data intact.

        The test covers the following scenarios:
        - Writing text data to the wrapper
        - Reading text data from the wrapper
        - Detaching the wrapper from the underlying file object
        - Verifying the data integrity after detachment

        """
        content = "vive l'été\n"
        with (
            tempfile.TemporaryFile() as temp,
            File(temp, name="something.txt") as test_file,
        ):
            test_file.write(content.encode())
            test_file.seek(0)
            wrapper = TextIOWrapper(test_file, "utf-8", newline="\n")
            self.assertEqual(wrapper.read(), content)
            wrapper.write(content)
            wrapper.seek(0)
            self.assertEqual(wrapper.read(), content * 2)
            test_file = wrapper.detach()
            test_file.seek(0)
            self.assertEqual(test_file.read(), (content * 2).encode())

    def test_exclusive_lock(self):
        """

        Tests the behavior of acquiring and releasing an exclusive lock on a file.

        This test case validates the following scenarios:

        * Acquiring an exclusive lock on a file returns True.
        * Attempting to acquire an exclusive non-blocking lock on a file that is already locked returns False.
        * Attempting to acquire a shared non-blocking lock on a file that is exclusively locked returns False.
        * Releasing an exclusive lock on a file returns True.

        The test ensures that the locking mechanism correctly handles concurrent access to a file and enforces exclusive locking semantics. 
        """
        file_path = Path(__file__).parent / "test.png"
        with open(file_path) as f1, open(file_path) as f2:
            self.assertIs(locks.lock(f1, locks.LOCK_EX), True)
            self.assertIs(locks.lock(f2, locks.LOCK_EX | locks.LOCK_NB), False)
            self.assertIs(locks.lock(f2, locks.LOCK_SH | locks.LOCK_NB), False)
            self.assertIs(locks.unlock(f1), True)

    def test_shared_lock(self):
        file_path = Path(__file__).parent / "test.png"
        with open(file_path) as f1, open(file_path) as f2:
            self.assertIs(locks.lock(f1, locks.LOCK_SH), True)
            self.assertIs(locks.lock(f2, locks.LOCK_SH | locks.LOCK_NB), True)
            self.assertIs(locks.unlock(f1), True)
            self.assertIs(locks.unlock(f2), True)

    def test_open_supports_full_signature(self):
        called = False

        def opener(path, flags):
            """

            Opens a file and sets a flag indicating that the operation has been performed.

            :param path: The path to the file to be opened.
            :param flags: The flags to be used when opening the file, as specified by the os module.

            :return: The file descriptor of the opened file.

            :note: Also sets a non-local flag `called` to True, indicating that the open operation has been initiated.

            """
            nonlocal called
            called = True
            return os.open(path, flags)

        file_path = Path(__file__).parent / "test.png"
        with open(file_path) as f:
            test_file = File(f)

        with test_file.open(opener=opener):
            self.assertIs(called, True)


class NoNameFileTestCase(unittest.TestCase):
    """
    Other examples of unnamed files may be tempfile.SpooledTemporaryFile or
    urllib.urlopen()
    """

    def test_noname_file_default_name(self):
        self.assertIsNone(File(BytesIO(b"A file with no name")).name)

    def test_noname_file_get_size(self):
        self.assertEqual(File(BytesIO(b"A file with no name")).size, 19)


class ContentFileTestCase(unittest.TestCase):
    def test_content_file_default_name(self):
        self.assertIsNone(ContentFile(b"content").name)

    def test_content_file_custom_name(self):
        """
        The constructor of ContentFile accepts 'name' (#16590).
        """
        name = "I can have a name too!"
        self.assertEqual(ContentFile(b"content", name=name).name, name)

    def test_content_file_input_type(self):
        """
        ContentFile can accept both bytes and strings and the retrieved content
        is of the same type.
        """
        self.assertIsInstance(ContentFile(b"content").read(), bytes)
        self.assertIsInstance(ContentFile("español").read(), str)

    def test_open_resets_file_to_start_and_returns_context_manager(self):
        file = ContentFile(b"content")
        with file.open() as f:
            self.assertEqual(f.read(), b"content")
        with file.open() as f:
            self.assertEqual(f.read(), b"content")

    def test_size_changing_after_writing(self):
        """ContentFile.size changes after a write()."""
        f = ContentFile("")
        self.assertEqual(f.size, 0)
        f.write("Test ")
        f.write("string")
        self.assertEqual(f.size, 11)
        with f.open() as fh:
            self.assertEqual(fh.read(), "Test string")


class InMemoryUploadedFileTests(unittest.TestCase):
    def test_open_resets_file_to_start_and_returns_context_manager(self):
        """
        Tests that opening an InMemoryUploadedFile resets its file pointer to the start 
        and returns a context manager for reading the file's contents.

        Verifies that a previously read file can be reopened and its contents retrieved 
        again, ensuring that the file's state is properly reset. This is essential for 
        handling files that need to be processed multiple times, such as during upload 
        validation or processing. The test covers a key aspect of working with 
        InMemoryUploadedFile instances, providing assurance that they behave as expected 
        in common use cases.
        """
        uf = InMemoryUploadedFile(StringIO("1"), "", "test", "text/plain", 1, "utf8")
        uf.read()
        with uf.open() as f:
            self.assertEqual(f.read(), "1")


class TemporaryUploadedFileTests(unittest.TestCase):
    def test_extension_kept(self):
        """The temporary file name has the same suffix as the original file."""
        with TemporaryUploadedFile("test.txt", "text/plain", 1, "utf8") as temp_file:
            self.assertTrue(temp_file.file.name.endswith(".upload.txt"))

    def test_file_upload_temp_dir_pathlib(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with override_settings(FILE_UPLOAD_TEMP_DIR=Path(tmp_dir)):
                with TemporaryUploadedFile(
                    "test.txt", "text/plain", 1, "utf-8"
                ) as temp_file:
                    self.assertTrue(os.path.exists(temp_file.file.name))


class DimensionClosingBug(unittest.TestCase):
    """
    get_image_dimensions() properly closes files (#8817)
    """

    @unittest.skipUnless(Image, "Pillow not installed")
    def test_not_closing_of_files(self):
        """
        Open files passed into get_image_dimensions() should stay opened.
        """
        empty_io = BytesIO()
        try:
            images.get_image_dimensions(empty_io)
        finally:
            self.assertTrue(not empty_io.closed)

    @unittest.skipUnless(Image, "Pillow not installed")
    def test_closing_of_filenames(self):
        """
        get_image_dimensions() called with a filename should closed the file.
        """
        # We need to inject a modified open() builtin into the images module
        # that checks if the file was closed properly if the function is
        # called with a filename instead of a file object.
        # get_image_dimensions will call our catching_open instead of the
        # regular builtin one.

        class FileWrapper:
            _closed = []

            def __init__(self, f):
                self.f = f

            def __getattr__(self, name):
                return getattr(self.f, name)

            def close(self):
                self._closed.append(True)
                self.f.close()

        def catching_open(*args):
            return FileWrapper(open(*args))

        images.open = catching_open
        try:
            images.get_image_dimensions(
                os.path.join(os.path.dirname(__file__), "test1.png")
            )
        finally:
            del images.open
        self.assertTrue(FileWrapper._closed)


class InconsistentGetImageDimensionsBug(unittest.TestCase):
    """
    get_image_dimensions() works properly after various calls
    using a file handler (#11158)
    """

    @unittest.skipUnless(Image, "Pillow not installed")
    def test_multiple_calls(self):
        """
        Multiple calls of get_image_dimensions() should return the same size.
        """
        img_path = os.path.join(os.path.dirname(__file__), "test.png")
        with open(img_path, "rb") as fh:
            image = images.ImageFile(fh)
            image_pil = Image.open(fh)
            size_1 = images.get_image_dimensions(image)
            size_2 = images.get_image_dimensions(image)
        self.assertEqual(image_pil.size, size_1)
        self.assertEqual(size_1, size_2)

    @unittest.skipUnless(Image, "Pillow not installed")
    def test_bug_19457(self):
        """
        Regression test for #19457
        get_image_dimensions() fails on some PNGs, while Image.size is working
        good on them.
        """
        img_path = os.path.join(os.path.dirname(__file__), "magic.png")
        size = images.get_image_dimensions(img_path)
        with open(img_path, "rb") as fh:
            self.assertEqual(size, Image.open(fh).size)


@unittest.skipUnless(Image, "Pillow not installed")
class GetImageDimensionsTests(unittest.TestCase):
    def test_invalid_image(self):
        """
        get_image_dimensions() should return (None, None) for the dimensions of
        invalid images (#24441).

        brokenimg.png is not a valid image and it has been generated by:
        $ echo "123" > brokenimg.png
        """
        img_path = os.path.join(os.path.dirname(__file__), "brokenimg.png")
        with open(img_path, "rb") as fh:
            size = images.get_image_dimensions(fh)
            self.assertEqual(size, (None, None))

    def test_valid_image(self):
        """
        get_image_dimensions() should catch struct.error while feeding the PIL
        Image parser (#24544).

        Emulates the Parser feed error. Since the error is raised on every feed
        attempt, the resulting image size should be invalid: (None, None).
        """
        img_path = os.path.join(os.path.dirname(__file__), "test.png")
        with mock.patch("PIL.ImageFile.Parser.feed", side_effect=struct.error):
            with open(img_path, "rb") as fh:
                size = images.get_image_dimensions(fh)
                self.assertEqual(size, (None, None))

    def test_missing_file(self):
        size = images.get_image_dimensions("missing.png")
        self.assertEqual(size, (None, None))

    @unittest.skipUnless(HAS_WEBP, "WEBP not installed")
    def test_webp(self):
        """

        Tests the functionality of getting image dimensions for a WEBP image file.

        This test checks if the images module can successfully retrieve the dimensions
        of a WEBP image. It uses a test image file named 'test.webp' and verifies that
        the retrieved dimensions match the expected size.

        The test is skipped if the WEBP library is not installed.

        """
        img_path = os.path.join(os.path.dirname(__file__), "test.webp")
        with open(img_path, "rb") as fh:
            size = images.get_image_dimensions(fh)
        self.assertEqual(size, (540, 405))


class FileMoveSafeTests(unittest.TestCase):
    def test_file_move_overwrite(self):
        """
        Test that the file_move_safe function handles moving a file over an existing destination file with and without overwriting.

        The function validates the behavior of file_move_safe in two scenarios:
        - When allow_overwrite is False, it ensures a FileExistsError is raised when the destination file already exists.
        - When allow_overwrite is True, it verifies that the function successfully overwrites the destination file without raising an exception.
        """
        handle_a, self.file_a = tempfile.mkstemp()
        handle_b, self.file_b = tempfile.mkstemp()

        # file_move_safe() raises FileExistsError if the destination file
        # exists and allow_overwrite is False.
        msg = r"Destination file .* exists and allow_overwrite is False\."
        with self.assertRaisesRegex(FileExistsError, msg):
            file_move_safe(self.file_a, self.file_b, allow_overwrite=False)

        # should allow it and continue on if allow_overwrite is True
        self.assertIsNone(
            file_move_safe(self.file_a, self.file_b, allow_overwrite=True)
        )

        os.close(handle_a)
        os.close(handle_b)

    def test_file_move_permissionerror(self):
        """
        file_move_safe() ignores PermissionError thrown by copystat() and
        copymode().
        For example, PermissionError can be raised when the destination
        filesystem is CIFS, or when relabel is disabled by SELinux across
        filesystems.
        """
        permission_error = PermissionError(errno.EPERM, "msg")
        os_error = OSError("msg")
        handle_a, self.file_a = tempfile.mkstemp()
        handle_b, self.file_b = tempfile.mkstemp()
        handle_c, self.file_c = tempfile.mkstemp()
        try:
            # This exception is required to reach the copystat() call in
            # file_safe_move().
            with mock.patch("django.core.files.move.os.rename", side_effect=OSError()):
                # An error besides PermissionError isn't ignored.
                with mock.patch(
                    "django.core.files.move.copystat", side_effect=os_error
                ):
                    with self.assertRaises(OSError):
                        file_move_safe(self.file_a, self.file_b, allow_overwrite=True)
                # When copystat() throws PermissionError, copymode() error besides
                # PermissionError isn't ignored.
                with mock.patch(
                    "django.core.files.move.copystat", side_effect=permission_error
                ):
                    with mock.patch(
                        "django.core.files.move.copymode", side_effect=os_error
                    ):
                        with self.assertRaises(OSError):
                            file_move_safe(
                                self.file_a, self.file_b, allow_overwrite=True
                            )
                # PermissionError raised by copystat() is ignored.
                with mock.patch(
                    "django.core.files.move.copystat", side_effect=permission_error
                ):
                    self.assertIsNone(
                        file_move_safe(self.file_a, self.file_b, allow_overwrite=True)
                    )
                    # PermissionError raised by copymode() is ignored too.
                    with mock.patch(
                        "django.core.files.move.copymode", side_effect=permission_error
                    ):
                        self.assertIsNone(
                            file_move_safe(
                                self.file_c, self.file_b, allow_overwrite=True
                            )
                        )
        finally:
            os.close(handle_a)
            os.close(handle_b)
            os.close(handle_c)


class SpooledTempTests(unittest.TestCase):
    def test_in_memory_spooled_temp(self):
        with tempfile.SpooledTemporaryFile() as temp:
            temp.write(b"foo bar baz quux\n")
            django_file = File(temp, name="something.txt")
            self.assertEqual(django_file.size, 17)

    def test_written_spooled_temp(self):
        """
        Tests if a written and spooled temporary file has the correct size when wrapped in a Django File object.

        This test case checks the size of a temporary file after writing to it and ensures 
        that the size is correctly calculated when the file is used as a Django File object.
        The test verifies that the size property of the Django File object returns the 
        expected number of bytes written to the temporary file.
        """
        with tempfile.SpooledTemporaryFile(max_size=4) as temp:
            temp.write(b"foo bar baz quux\n")
            django_file = File(temp, name="something.txt")
            self.assertEqual(django_file.size, 17)
