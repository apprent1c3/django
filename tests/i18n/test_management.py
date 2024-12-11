import os

from django.core.management.commands.makemessages import TranslatableFile
from django.test import SimpleTestCase


class TranslatableFileTests(SimpleTestCase):
    def test_repr(self):
        """
        Tests the string representation of a TranslatableFile object.

        Verifies that the repr function returns a string in the expected format, 
        including the path to the file. This ensures that the object can be 
        effectively represented as a string for debugging or logging purposes.

        The expected output format is '<TranslatableFile: /path/to/file>'. The test 
        checks that the directory path and file name are correctly joined and 
        included in the string representation.
        """
        dirpath = "dir"
        file_name = "example"
        trans_file = TranslatableFile(
            dirpath=dirpath, file_name=file_name, locale_dir=None
        )
        self.assertEqual(
            repr(trans_file),
            "<TranslatableFile: %s>" % os.path.join(dirpath, file_name),
        )

    def test_eq(self):
        dirpath = "dir"
        file_name = "example"
        trans_file = TranslatableFile(
            dirpath=dirpath, file_name=file_name, locale_dir=None
        )
        trans_file_eq = TranslatableFile(
            dirpath=dirpath, file_name=file_name, locale_dir=None
        )
        trans_file_not_eq = TranslatableFile(
            dirpath="tmp", file_name=file_name, locale_dir=None
        )
        self.assertEqual(trans_file, trans_file_eq)
        self.assertNotEqual(trans_file, trans_file_not_eq)
