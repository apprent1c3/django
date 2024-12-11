from django.template.defaultfilters import filesizeformat
from django.test import SimpleTestCase
from django.utils import translation


class FunctionTests(SimpleTestCase):
    def test_formats(self):
        """
        Tests the filesizeformat function with various input values to ensure it correctly formats byte sizes into human-readable strings.

        The function is tested with a range of inputs, including different byte values, to verify that it accurately converts them into the corresponding units (bytes, KB, MB, GB, TB, PB).

        It also checks that the function handles invalid or edge-case inputs, such as complex numbers and strings, by returning a default value of '0 bytes'.

        The test cases cover various scenarios, including single bytes, kilobytes, megabytes, gigabytes, terabytes, and petabytes, as well as boundary values and non-numeric inputs. The test results are verified using assertions to ensure the expected output is returned for each input value.
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

        Test the functionality of filesizeformat with various input values.

        This test checks that the filesizeformat function correctly formats different sizes in bytes into human-readable strings, 
        using localized formats. The test cases cover a range of input values, including edge cases such as zero, negative numbers, 
        and non-integer values. The expected output for each test case is compared to the actual output of the filesizeformat function.

        Specifically, this test verifies that the function:

        * Handles different units (Bytes, KB, MB, GB, TB, PB) correctly
        * Formats numbers according to the localized format settings (in this case, German)
        * Returns the expected output for various input values, including boundary cases and invalid inputs

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
        tests = [
            (-1, "-1\xa0byte"),
            (-100, "-100\xa0bytes"),
            (-1024 * 1024 * 50, "-50.0\xa0MB"),
        ]
        for value, expected in tests:
            with self.subTest(value=value):
                self.assertEqual(filesizeformat(value), expected)
