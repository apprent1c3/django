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
        """
        Tests the generation of valid filenames from a given string, 
        ensuring that the generated filename is correctly sanitized and 
        normalized for various input scenarios, including absolute and 
        relative paths, and special characters.
        """
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
        Tests that the FileSystemStorage class correctly handles file paths that could potentially be used to access sensitive locations on the file system, such as parent directories or the current directory, and raises a SuspiciousFileOperation exception when encountering such paths.
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
        """
        Tests that FileSystemStorage correctly identifies and prevents path traversal attempts via directory names.

        This test case ensures that the storage system raises a SuspiciousFileOperation exception when given file names that could be used to traverse the file system, including those with relative paths ('..') and absolute paths ('/tmp/..').
        """
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
        """
        Tests the handling of potentially dangerous filenames by the FileField.

        Verifies that the generate_filename method raises a SuspiciousFileOperation
        exception when given filenames that could be used to access or write to
        sensitive system locations or cause other security issues.
        """
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
        f = FileField(upload_to="some/folder/")
        msg = "Detected path traversal attempt in 'some/folder/../path'"
        with self.assertRaisesMessage(SuspiciousFileOperation, msg):
            f.generate_filename(None, "../path")

    def test_filefield_generate_filename_absolute_path(self):
        """
        Tests that FileField.generate_filename prevents absolute path traversal attempts by raising a SuspiciousFileOperation exception.
        """
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
        f = FileField(upload_to="some/folder/")
        self.assertEqual(
            f.generate_filename(None, "test with space.txt"),
            os.path.normpath("some/folder/test_with_space.txt"),
        )

    def test_filefield_generate_filename_with_upload_to(self):
        def upload_to(instance, filename):
            return "some/folder/" + filename

        f = FileField(upload_to=upload_to)
        self.assertEqual(
            f.generate_filename(None, "test with space.txt"),
            os.path.normpath("some/folder/test_with_space.txt"),
        )

    def test_filefield_generate_filename_upload_to_overrides_dangerous_filename(self):
        """
        Verifies that a FileField's upload_to function takes precedence over potentially dangerous filenames, ensuring that generated filenames are safe and consistent.
        """
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
        """
        Tests that the generate_filename method of a FileField correctly identifies and raises an exception for path traversal attempts when the upload_to parameter is set to an absolute path.
        """
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
        """
        Tests that FileField raises a SuspiciousFileOperation when given a potentially 
        dangerous filename, ensuring security against directory traversal attacks.
        """
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
        Tests the compatibility of a Django FileField with an S3 storage system, ensuring that file paths and keys are properly generated and saved without relying on os.path calls.
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
