from django.template.defaultfilters import get_digit
from django.test import SimpleTestCase


class FunctionTests(SimpleTestCase):
    def test_values(self):
        """
        Tests the functionality of retrieving specific digits from a given integer value.

        This function verifies that the get_digit function correctly extracts digits 
        from an integer at specified positions. It checks the retrieval of digits 
        from different positions, including edge cases where the position is 
        greater than the number of digits in the integer. The test cases ensure 
        that the function behaves as expected and returns the correct digit or 
        a default value when the position exceeds the number of digits.
        """
        self.assertEqual(get_digit(123, 1), 3)
        self.assertEqual(get_digit(123, 2), 2)
        self.assertEqual(get_digit(123, 3), 1)
        self.assertEqual(get_digit(123, 4), 0)
        self.assertEqual(get_digit(123, 0), 123)

    def test_string(self):
        self.assertEqual(get_digit("xyz", 0), "xyz")
