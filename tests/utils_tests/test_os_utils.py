import os
import unittest
from pathlib import Path

from django.core.exceptions import SuspiciousFileOperation
from django.utils._os import safe_join, to_path


class SafeJoinTests(unittest.TestCase):
    def test_base_path_ends_with_sep(self):
        """
        Determines if the base path ends with a separator as expected.

        This test case checks if the joining of paths using a safe method results in a base path that correctly terminates with a path separator, ensuring consistency and accuracy in path construction. 

        Args:
            None

        Returns:
            None 

        Raises:
            AssertionError: If the base path does not end with the expected path separator.
        """
        drive, path = os.path.splitdrive(safe_join("/abc/", "abc"))
        self.assertEqual(path, "{0}abc{0}abc".format(os.path.sep))

    def test_root_path(self):
        drive, path = os.path.splitdrive(safe_join("/", "path"))
        self.assertEqual(
            path,
            "{}path".format(os.path.sep),
        )

        drive, path = os.path.splitdrive(safe_join("/", ""))
        self.assertEqual(
            path,
            os.path.sep,
        )

    def test_parent_path(self):
        with self.assertRaises(SuspiciousFileOperation):
            safe_join("/abc/", "../def")


class ToPathTests(unittest.TestCase):
    def test_to_path(self):
        for path in ("/tmp/some_file.txt", Path("/tmp/some_file.txt")):
            with self.subTest(path):
                self.assertEqual(to_path(path), Path("/tmp/some_file.txt"))

    def test_to_path_invalid_value(self):
        """
        Tests that the to_path function raises a TypeError when given an invalid value.

        This test case checks that the function behaves correctly when passed an argument of the wrong type, specifically an integer.

        :raises TypeError: if the input value is not a valid path
        """
        with self.assertRaises(TypeError):
            to_path(42)
