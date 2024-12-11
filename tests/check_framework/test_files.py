from pathlib import Path

from django.core.checks import Error
from django.core.checks.files import check_setting_file_upload_temp_dir
from django.test import SimpleTestCase


class FilesCheckTests(SimpleTestCase):
    def test_file_upload_temp_dir(self):
        """
        Tests the file upload temporary directory setting to ensure it handles different input types correctly.

        The function tests the setting with various input values, including None, an empty string, the current working directory as a Path object, and the current working directory as a string. It verifies that the check_setting_file_upload_temp_dir function returns an empty list for each of these input values, indicating successful validation.

        This test covers the edge cases for the file upload temporary directory setting, ensuring that the application behaves as expected under different configuration scenarios.
        """
        tests = [
            None,
            "",
            Path.cwd(),
            str(Path.cwd()),
        ]
        for setting in tests:
            with self.subTest(setting), self.settings(FILE_UPLOAD_TEMP_DIR=setting):
                self.assertEqual(check_setting_file_upload_temp_dir(None), [])

    def test_file_upload_temp_dir_nonexistent(self):
        for setting in ["nonexistent", Path("nonexistent")]:
            with self.subTest(setting), self.settings(FILE_UPLOAD_TEMP_DIR=setting):
                self.assertEqual(
                    check_setting_file_upload_temp_dir(None),
                    [
                        Error(
                            "The FILE_UPLOAD_TEMP_DIR setting refers to the "
                            "nonexistent directory 'nonexistent'.",
                            id="files.E001",
                        ),
                    ],
                )
