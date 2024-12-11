import os

from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.db.models import FileField
from django.test import SimpleTestCase


class AWSS3Storage(Storage):
    """
    Simulate an AWS S3 storage which uses Unix-like paths and allows any
    characters in file names but where there aren't actual folders but just
    keys.
    """

    prefix = "mys3folder/"

    def _save(self, name, content):
        """
        This method is important to test that Storage.save() doesn't replace
        '\' with '/' (rather FileSystemStorage.save() does).
        """
        return name

    def get_valid_name(self, name):
        return name

    def get_available_name(self, name, max_length=None):
        return name

    def generate_filename(self, filename):
        """
        This is the method that's important to override when using S3 so that
        os.path() isn't called, which would break S3 keys.
        """
        return self.prefix + self.get_valid_name(filename)


class StorageGenerateFilenameTests(SimpleTestCase):
    """Tests for base Storage's generate_filename method."""

    storage_class = Storage

    def test_valid_names(self):
        storage = self.storage_class()
        name = "UnTRIVíAL @fil$ena#me!"
        valid_name = storage.get_valid_name(name)
        candidates = [
            (name, valid_name),
            (f"././././././{name}", valid_name),
            (f"some/path/{name}", f"some/path/{valid_name}"),
            (f"some/./path/./{name}", f"some/path/{valid_name}"),
            (f"././some/././path/./{name}", f"some/path/{valid_name}"),
            (f".\\.\\.\\.\\.\\.\\{name}", valid_name),
            (f"some\\path\\{name}", f"some/path/{valid_name}"),
            (f"some\\.\\path\\.\\{name}", f"some/path/{valid_name}"),
            (f".\\.\\some\\.\\.\\path\\.\\{name}", f"some/path/{valid_name}"),
        ]
        for name, expected in candidates:
            with self.subTest(name=name):
                result = storage.generate_filename(name)
                self.assertEqual(result, os.path.normpath(expected))


class FileSystemStorageGenerateFilenameTests(StorageGenerateFilenameTests):

    storage_class = FileSystemStorage


class GenerateFilenameStorageTests(SimpleTestCase):
    def test_storage_dangerous_paths(self):
        """

        Tests the handling of potentially dangerous file paths in the FileSystemStorage class.

        This test case checks that the get_available_name and generate_filename methods
        raise a SuspiciousFileOperation exception when given file paths that could be
        used to access files outside of the intended storage directory.

        The test covers a range of potentially malicious file paths, including those
        containing '..' and '.' directory traversal characters, as well as absolute and
        relative paths. It verifies that the FileSystemStorage class correctly detects
        and prevents these potentially dangerous file operations, both with and without
        the allow_overwrite option enabled.

        """
        candidates = [
            ("/tmp/..", ".."),
            ("\\tmp\\..", ".."),
            ("/tmp/.", "."),
            ("\\tmp\\.", "."),
            ("..", ".."),
            (".", "."),
            ("", ""),
        ]
        s = FileSystemStorage()
        s_overwrite = FileSystemStorage(allow_overwrite=True)
        msg = "Could not derive file name from '%s'"
        for file_name, base_name in candidates:
            with self.subTest(file_name=file_name):
                with self.assertRaisesMessage(SuspiciousFileOperation, msg % base_name):
                    s.get_available_name(file_name)
                with self.assertRaisesMessage(SuspiciousFileOperation, msg % base_name):
                    s_overwrite.get_available_name(file_name)
                with self.assertRaisesMessage(SuspiciousFileOperation, msg % base_name):
                    s.generate_filename(file_name)

    def test_storage_dangerous_paths_dir_name(self):
        candidates = [
            ("../path", ".."),
            ("..\\path", ".."),
            ("tmp/../path", "tmp/.."),
            ("tmp\\..\\path", "tmp/.."),
            ("/tmp/../path", "/tmp/.."),
            ("\\tmp\\..\\path", "/tmp/.."),
        ]
        s = FileSystemStorage()
        s_overwrite = FileSystemStorage(allow_overwrite=True)
        for file_name, path in candidates:
            msg = "Detected path traversal attempt in '%s'" % path
            with self.subTest(file_name=file_name):
                with self.assertRaisesMessage(SuspiciousFileOperation, msg):
                    s.get_available_name(file_name)
                with self.assertRaisesMessage(SuspiciousFileOperation, msg):
                    s_overwrite.get_available_name(file_name)
                with self.assertRaisesMessage(SuspiciousFileOperation, msg):
                    s.generate_filename(file_name)

    def test_filefield_dangerous_filename(self):
        candidates = [
            ("..", "some/folder/.."),
            (".", "some/folder/."),
            ("", "some/folder/"),
            ("???", "???"),
            ("$.$.$", "$.$.$"),
        ]
        f = FileField(upload_to="some/folder/")
        for file_name, msg_file_name in candidates:
            msg = f"Could not derive file name from '{msg_file_name}'"
            with self.subTest(file_name=file_name):
                with self.assertRaisesMessage(SuspiciousFileOperation, msg):
                    f.generate_filename(None, file_name)

    def test_filefield_dangerous_filename_dot_segments(self):
        """
        Tests that the FileField class correctly detects and prevents path traversal attempts
        when generating filenames with dot segments.

        The function verifies that a SuspiciousFileOperation exception is raised when a potentially
        dangerous filename is provided, ensuring the security and integrity of file uploads.

        :raises: SuspiciousFileOperation if a path traversal attempt is detected
        """
        f = FileField(upload_to="some/folder/")
        msg = "Detected path traversal attempt in 'some/folder/../path'"
        with self.assertRaisesMessage(SuspiciousFileOperation, msg):
            f.generate_filename(None, "../path")

    def test_filefield_generate_filename_absolute_path(self):
        f = FileField(upload_to="some/folder/")
        candidates = [
            "/tmp/path",
            "/tmp/../path",
        ]
        for file_name in candidates:
            msg = f"Detected path traversal attempt in '{file_name}'"
            with self.subTest(file_name=file_name):
                with self.assertRaisesMessage(SuspiciousFileOperation, msg):
                    f.generate_filename(None, file_name)

    def test_filefield_generate_filename(self):
        """

        Generates a filename for a file being uploaded through a :class:`FileField`.

        This method takes into account the upload directory specified in the :class:`FileField`
        instance and sanitizes the filename by replacing spaces with underscores, ensuring a valid
        path is created.

        The generated filename is then normalized using the system's path normalization rules.

        :param None: The instance the file is being uploaded to (not used in this implementation)
        :param str: The original filename of the uploaded file
        :return: A normalized path to the generated filename

        """
        f = FileField(upload_to="some/folder/")
        self.assertEqual(
            f.generate_filename(None, "test with space.txt"),
            os.path.normpath("some/folder/test_with_space.txt"),
        )

    def test_filefield_generate_filename_with_upload_to(self):
        """
        Tests the generation of a filename for a FileField when the upload_to parameter is specified.

        This test case verifies that the filename is correctly generated based on the upload_to function.
        The function is expected to return a string that represents the path where the file should be uploaded.
        In this case, the upload_to function returns a path with a fixed directory and the original filename.
        The test checks that the generated filename is correctly formatted and that spaces in the original filename are properly replaced with underscores, and then normalized using the os.path.normpath function.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        AssertionError
            If the generated filename does not match the expected result.

        """
        def upload_to(instance, filename):
            return "some/folder/" + filename

        f = FileField(upload_to=upload_to)
        self.assertEqual(
            f.generate_filename(None, "test with space.txt"),
            os.path.normpath("some/folder/test_with_space.txt"),
        )

    def test_filefield_generate_filename_upload_to_overrides_dangerous_filename(self):
        def upload_to(instance, filename):
            return "test.txt"

        f = FileField(upload_to=upload_to)
        candidates = [
            "/tmp/.",
            "/tmp/..",
            "/tmp/../path",
            "/tmp/path",
            "some/folder/",
            "some/folder/.",
            "some/folder/..",
            "some/folder/???",
            "some/folder/$.$.$",
            "some/../test.txt",
            "",
        ]
        for file_name in candidates:
            with self.subTest(file_name=file_name):
                self.assertEqual(f.generate_filename(None, file_name), "test.txt")

    def test_filefield_generate_filename_upload_to_absolute_path(self):
        def upload_to(instance, filename):
            return "/tmp/" + filename

        f = FileField(upload_to=upload_to)
        candidates = [
            "path",
            "../path",
            "???",
            "$.$.$",
        ]
        for file_name in candidates:
            msg = f"Detected path traversal attempt in '/tmp/{file_name}'"
            with self.subTest(file_name=file_name):
                with self.assertRaisesMessage(SuspiciousFileOperation, msg):
                    f.generate_filename(None, file_name)

    def test_filefield_generate_filename_upload_to_dangerous_filename(self):
        def upload_to(instance, filename):
            return "/tmp/" + filename

        f = FileField(upload_to=upload_to)
        candidates = ["..", ".", ""]
        for file_name in candidates:
            msg = f"Could not derive file name from '/tmp/{file_name}'"
            with self.subTest(file_name=file_name):
                with self.assertRaisesMessage(SuspiciousFileOperation, msg):
                    f.generate_filename(None, file_name)

    def test_filefield_awss3_storage(self):
        """
        Simulate a FileField with an S3 storage which uses keys rather than
        folders and names. FileField and Storage shouldn't have any os.path()
        calls that break the key.
        """
        storage = AWSS3Storage()
        folder = "not/a/folder/"

        f = FileField(upload_to=folder, storage=storage)
        key = "my-file-key\\with odd characters"
        data = ContentFile("test")
        expected_key = AWSS3Storage.prefix + folder + key

        # Simulate call to f.save()
        result_key = f.generate_filename(None, key)
        self.assertEqual(result_key, expected_key)

        result_key = storage.save(result_key, data)
        self.assertEqual(result_key, expected_key)

        # Repeat test with a callable.
        def upload_to(instance, filename):
            # Return a non-normalized path on purpose.
            return folder + filename

        f = FileField(upload_to=upload_to, storage=storage)

        # Simulate call to f.save()
        result_key = f.generate_filename(None, key)
        self.assertEqual(result_key, expected_key)

        result_key = storage.save(result_key, data)
        self.assertEqual(result_key, expected_key)
