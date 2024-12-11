import os.path

from django.core.exceptions import ValidationError
from django.forms import FilePathField
from django.test import SimpleTestCase

PATH = os.path.dirname(os.path.abspath(__file__))


def fix_os_paths(x):
    """
    Fixes operating system paths by removing a prefix and converting backslashes to forward slashes.

    This function takes an input `x` and applies the following transformations:
    - If `x` is a string, it removes a predefined prefix (`PATH`) from the start of the string and replaces any backslashes with forward slashes.
    - If `x` is a tuple or list, it recursively applies the same transformations to each element.
    - If `x` is of any other type, it is returned unchanged.

    The result is a modified version of the input with operating system paths standardized to use forward slashes.
    """
    if isinstance(x, str):
        return x.removeprefix(PATH).replace("\\", "/")
    elif isinstance(x, tuple):
        return tuple(fix_os_paths(list(x)))
    elif isinstance(x, list):
        return [fix_os_paths(y) for y in x]
    else:
        return x


class FilePathFieldTest(SimpleTestCase):
    expected_choices = [
        ("/filepathfield_test_dir/__init__.py", "__init__.py"),
        ("/filepathfield_test_dir/a.py", "a.py"),
        ("/filepathfield_test_dir/ab.py", "ab.py"),
        ("/filepathfield_test_dir/b.py", "b.py"),
        ("/filepathfield_test_dir/c/__init__.py", "__init__.py"),
        ("/filepathfield_test_dir/c/d.py", "d.py"),
        ("/filepathfield_test_dir/c/e.py", "e.py"),
        ("/filepathfield_test_dir/c/f/__init__.py", "__init__.py"),
        ("/filepathfield_test_dir/c/f/g.py", "g.py"),
        ("/filepathfield_test_dir/h/__init__.py", "__init__.py"),
        ("/filepathfield_test_dir/j/__init__.py", "__init__.py"),
    ]
    path = os.path.join(PATH, "filepathfield_test_dir") + "/"

    def assertChoices(self, field, expected_choices):
        self.assertEqual(fix_os_paths(field.choices), expected_choices)

    def test_fix_os_paths(self):
        self.assertEqual(fix_os_paths(self.path), ("/filepathfield_test_dir/"))

    def test_nonexistent_path(self):
        with self.assertRaisesMessage(FileNotFoundError, "nonexistent"):
            FilePathField(path="nonexistent")

    def test_no_options(self):
        f = FilePathField(path=self.path)
        expected = [
            ("/filepathfield_test_dir/README", "README"),
        ] + self.expected_choices[:4]
        self.assertChoices(f, expected)

    def test_clean(self):
        """
        Tests the clean method of a FilePathField instance.

        This method checks if the clean method correctly validates file paths and raises 
        a ValidationError when an invalid file path is provided. It also verifies that 
        the method returns the expected cleaned file path when a valid file path is given.

        The test case specifically checks for two scenarios:
        - An invalid file path, which should raise a ValidationError with a specific message.
        - A valid file path, which should be cleaned and returned in a standardized format, 
          with operating system-specific path separators normalized to Unix-style forward slashes.
        """
        f = FilePathField(path=self.path)
        msg = "'Select a valid choice. a.py is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("a.py")
        self.assertEqual(
            fix_os_paths(f.clean(self.path + "a.py")), "/filepathfield_test_dir/a.py"
        )

    def test_match(self):
        f = FilePathField(path=self.path, match=r"^.*?\.py$")
        self.assertChoices(f, self.expected_choices[:4])

    def test_recursive(self):
        f = FilePathField(path=self.path, recursive=True, match=r"^.*?\.py$")
        expected = [
            ("/filepathfield_test_dir/__init__.py", "__init__.py"),
            ("/filepathfield_test_dir/a.py", "a.py"),
            ("/filepathfield_test_dir/ab.py", "ab.py"),
            ("/filepathfield_test_dir/b.py", "b.py"),
            ("/filepathfield_test_dir/c/__init__.py", "c/__init__.py"),
            ("/filepathfield_test_dir/c/d.py", "c/d.py"),
            ("/filepathfield_test_dir/c/e.py", "c/e.py"),
            ("/filepathfield_test_dir/c/f/__init__.py", "c/f/__init__.py"),
            ("/filepathfield_test_dir/c/f/g.py", "c/f/g.py"),
            ("/filepathfield_test_dir/h/__init__.py", "h/__init__.py"),
            ("/filepathfield_test_dir/j/__init__.py", "j/__init__.py"),
        ]
        self.assertChoices(f, expected)

    def test_allow_folders(self):
        f = FilePathField(path=self.path, allow_folders=True, allow_files=False)
        self.assertChoices(
            f,
            [
                ("/filepathfield_test_dir/c", "c"),
                ("/filepathfield_test_dir/h", "h"),
                ("/filepathfield_test_dir/j", "j"),
            ],
        )

    def test_recursive_no_folders_or_files(self):
        """

        Tests that a FilePathField with recursive set to True, but without allowing folders or files, 
        returns an empty list of choices.

        This test ensures that the FilePathField behaves correctly when its configuration prevents 
        it from including any files or subdirectories in the options.

        """
        f = FilePathField(
            path=self.path, recursive=True, allow_folders=False, allow_files=False
        )
        self.assertChoices(f, [])

    def test_recursive_folders_without_files(self):
        """
        Test that FilePathField returns the correct folder choices when recursive is True and only folders are allowed.

        This test case verifies that the FilePathField can recursively traverse a directory and return a list of subfolders, 
        excluding files. The function checks that the returned choices are correct and contain the expected paths and 
        human-readable names for the folders.

        The test uses a FilePathField instance with the recursive and allow_folders parameters set to True, and the 
        allow_files parameter set to False. The function then asserts that the choices returned by the field match 
        the expected list of folder paths and names.
        """
        f = FilePathField(
            path=self.path, recursive=True, allow_folders=True, allow_files=False
        )
        self.assertChoices(
            f,
            [
                ("/filepathfield_test_dir/c", "c"),
                ("/filepathfield_test_dir/h", "h"),
                ("/filepathfield_test_dir/j", "j"),
                ("/filepathfield_test_dir/c/f", "c/f"),
            ],
        )
