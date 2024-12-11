from django.template.defaultfilters import filesizeformat
from django.test import SimpleTestCase
from django.utils import translation


class FunctionTests(SimpleTestCase):
    def test_formats(self):
        """
        Tests the filesizeformat function to ensure it correctly formats file sizes.

        This test checks the function with a variety of input values, including integers representing different file sizes in bytes, 
        kilobytes (KB), megabytes (MB), gigabytes (GB), terabytes (TB), and petabytes (PB). Additionally, it checks the function's 
        behavior with non-integer inputs, such as complex numbers and strings. The test verifies that the function returns the 
        expected formatted string for each input value.

        The test cases cover the following scenarios:
        - Formatting of exact byte counts (e.g., 0 bytes, 1 byte, 1023 bytes)
        - Formatting of kilobyte, megabyte, gigabyte, terabyte, and petabyte values
        - Handling of non-numeric input values (e.g., complex numbers, strings)
        """
        tests = [
            (0, "0\xa0bytes"),
            (1, "1\xa0byte"),
            (1023, "1023\xa0bytes"),
            (1024, "1.0\xa0KB"),
            (10 * 1024, "10.0\xa0KB"),
            (1024 * 1024 - 1, "1024.0\xa0KB"),
            (1024 * 1024, "1.0\xa0MB"),
            (1024 * 1024 * 50, "50.0\xa0MB"),
            (1024 * 1024 * 1024 - 1, "1024.0\xa0MB"),
            (1024 * 1024 * 1024, "1.0\xa0GB"),
            (1024 * 1024 * 1024 * 1024, "1.0\xa0TB"),
            (1024 * 1024 * 1024 * 1024 * 1024, "1.0\xa0PB"),
            (1024 * 1024 * 1024 * 1024 * 1024 * 2000, "2000.0\xa0PB"),
            (complex(1, -1), "0\xa0bytes"),
            ("", "0\xa0bytes"),
            ("\N{GREEK SMALL LETTER ALPHA}", "0\xa0bytes"),
        ]
        for value, expected in tests:
            with self.subTest(value=value):
                self.assertEqual(filesizeformat(value), expected)

    def test_localized_formats(self):
        """
        Tests the filesizeformat function with various input values to ensure correct localization and formatting.

        The test covers a range of file sizes from 0 bytes to petabytes, as well as edge cases with non-numeric input values, all within a German locale ('de'). It verifies that the function returns the expected formatted string for each input value, using the correct unit (Bytes, KB, MB, GB, TB, PB) and formatting conventions for the specified locale.
        """
        tests = [
            (0, "0\xa0Bytes"),
            (1, "1\xa0Byte"),
            (1023, "1023\xa0Bytes"),
            (1024, "1,0\xa0KB"),
            (10 * 1024, "10,0\xa0KB"),
            (1024 * 1024 - 1, "1024,0\xa0KB"),
            (1024 * 1024, "1,0\xa0MB"),
            (1024 * 1024 * 50, "50,0\xa0MB"),
            (1024 * 1024 * 1024 - 1, "1024,0\xa0MB"),
            (1024 * 1024 * 1024, "1,0\xa0GB"),
            (1024 * 1024 * 1024 * 1024, "1,0\xa0TB"),
            (1024 * 1024 * 1024 * 1024 * 1024, "1,0\xa0PB"),
            (1024 * 1024 * 1024 * 1024 * 1024 * 2000, "2000,0\xa0PB"),
            (complex(1, -1), "0\xa0Bytes"),
            ("", "0\xa0Bytes"),
            ("\N{GREEK SMALL LETTER ALPHA}", "0\xa0Bytes"),
        ]
        with translation.override("de"):
            for value, expected in tests:
                with self.subTest(value=value):
                    self.assertEqual(filesizeformat(value), expected)

    def test_negative_numbers(self):
        """
        Tests the filesizeformat function with negative input numbers.

        This test case checks that the function correctly handles negative numbers and returns the expected formatted string. It covers a range of negative values, including small and large numbers, to ensure the function behaves as expected in different scenarios. The test verifies that the function returns the correct formatted string for each input value, including the correct unit (e.g., bytes, MB).
        """
        tests = [
            (-1, "-1\xa0byte"),
            (-100, "-100\xa0bytes"),
            (-1024 * 1024 * 50, "-50.0\xa0MB"),
        ]
        for value, expected in tests:
            with self.subTest(value=value):
                self.assertEqual(filesizeformat(value), expected)
