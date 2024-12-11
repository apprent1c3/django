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

        Test the generate_filename method of the storage class to ensure it correctly
        handles and sanitizes file names with special characters and paths.

        The test checks various file name scenarios, including names with special characters,
        absolute and relative paths, and names with redundant or escaped path separators.
        It verifies that the method produces a consistent and normalized output, following
        the expected naming conventions. This test case ensures the storage class can
        reliably generate valid file names from different input formats.

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

        Tests the functionality of FileSystemStorage to handle potentially dangerous file paths.

        This function checks that the storage mechanism correctly identifies and raises an exception
        when encountering file paths that attempt to traverse outside of the designated storage area.
        Specifically, it tests paths that contain parent directory references ('..') and current directory
        references ('.').

        The function validates this behavior for both normal storage and storage that allows overwriting
        of existing files, ensuring that security checks are performed consistently across different
        storage configurations.

        By verifying that suspicious file operations are correctly detected and reported, this test
        helps ensure the integrity and security of the file storage system.

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

        Tests the FileSystemStorage class to ensure it prevents path traversal attacks by raising a SuspiciousFileOperation exception 
        when provided with a file name that contains a potentially malicious directory path.

        The function checks various file name and directory path combinations, including those with relative paths ('..' and '.\\') 
        and absolute paths, to verify that the get_available_name and generate_filename methods correctly identify and prevent 
        these types of attacks. It also tests the behavior when the allow_overwrite parameter is set to True. 

        The test cases cover different operating system path separators to ensure the function works correctly across various platforms.

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
        """
        Tests the generation of a filename for a FileField instance when the upload_to parameter is set.

        This test case verifies that the filename is correctly generated by appending the provided filename to the path specified in the upload_to function, and that any spaces in the filename are replaced with underscores to ensure a valid path.

        The expected output is a normalized path that combines the upload_to path with the modified filename, ensuring consistency and correctness in file naming conventions.
        """
        def upload_to(instance, filename):
            return "some/folder/" + filename

        f = FileField(upload_to=upload_to)
        self.assertEqual(
            f.generate_filename(None, "test with space.txt"),
            os.path.normpath("some/folder/test_with_space.txt"),
        )

    def test_filefield_generate_filename_upload_to_overrides_dangerous_filename(self):
        """

        Tests that the generate_filename method of a FileField instance overrides potentially
        dangerous filenames with a safe one specified by the upload_to callback.

        The upload_to callback is used to provide a customized filename for file uploads.
        In this case, it always returns 'test.txt', regardless of the original filename.
        This ensures that even if a malicious user attempts to upload a file with a
        potentially dangerous filename, the file will be saved with a safe and controlled name.

        The test covers a range of candidate filenames, including those with potential
        security vulnerabilities such as relative paths, hidden files, and specially crafted
        filenames. The test asserts that the generate_filename method correctly overrides
        these filenames with the safe one specified by the upload_to callback.

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

        Tests that the FileField's generate_filename method properly handles 
        potentially malicious filenames that could lead to security vulnerabilities.

        Specifically, this test checks that the method raises a SuspiciousFileOperation 
        exception when attempting to generate a filename from a path that contains 
        relatives paths ('..', '.', or empty strings), which could potentially allow 
        an attacker to manipulate the file system.

        The test verifies that the correct error message is raised for each 
        problematic filename.

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
