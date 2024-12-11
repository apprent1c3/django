from django.template.defaultfilters import filesizeformat
from django.test import SimpleTestCase
from django.utils import translation


class FunctionTests(SimpleTestCase):
    def test_formats(self):
        """

        Tests the filesizeformat function by checking its output against various input values.

        The function verifies that the filesizeformat function correctly handles different units of file size measurement, including bytes, kilobytes (KB), megabytes (MB), gigabytes (GB), terabytes (TB), and petabytes (PB). It also checks the function's behavior with edge cases, such as zero, negative, and non-numeric input values.

        Expected input values range from 0 to very large numbers, and the test checks that the output is correctly formatted as a string with the corresponding unit. The test also covers non-numeric inputs, including complex numbers and strings, to ensure the function raises no errors and returns a reasonable result.

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
        Tests the `filesizeformat` function for correct formatting of file sizes in the locale 'de'. 
        The test cases cover a wide range of file sizes, from 0 bytes to petabytes, 
        as well as edge cases such as non-numeric input like complex numbers and strings.
        Check if the function returns the expected localized string representations.
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
        Tests the filesizeformat function with negative input values.

        Verifies that the function correctly handles negative numbers and returns the expected formatted string. 
        The test cases cover a range of negative values, from small integers to larger values representing megabytes.
        """
        tests = [
            (-1, "-1\xa0byte"),
            (-100, "-100\xa0bytes"),
            (-1024 * 1024 * 50, "-50.0\xa0MB"),
        ]
        for value, expected in tests:
            with self.subTest(value=value):
                self.assertEqual(filesizeformat(value), expected)
