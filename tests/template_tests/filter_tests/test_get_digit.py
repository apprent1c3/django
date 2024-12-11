from django.template.defaultfilters import get_digit
from django.test import SimpleTestCase


class FunctionTests(SimpleTestCase):
    def test_values(self):
        """
        Tests the get_digit function to retrieve digits at specific positions from an integer.

        The test cases cover various position values, including valid and out-of-bounds positions.
        The function's behavior for retrieving individual digits, as well as the entire number when
        an invalid position is specified, is verified to ensure correct functionality.

        Validates the following scenarios:

        * Retrieval of digits at specific positions (1-indexed from right to left)
        * Retrieval of the most significant digit when the position exceeds the number of digits
        * Handling of a position of 0, where the entire number is returned
        """
        self.assertEqual(get_digit(123, 1), 3)
        self.assertEqual(get_digit(123, 2), 2)
        self.assertEqual(get_digit(123, 3), 1)
        self.assertEqual(get_digit(123, 4), 0)
        self.assertEqual(get_digit(123, 0), 123)

    def test_string(self):
        self.assertEqual(get_digit("xyz", 0), "xyz")
