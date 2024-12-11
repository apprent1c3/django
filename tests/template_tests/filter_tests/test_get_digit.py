from django.template.defaultfilters import get_digit
from django.test import SimpleTestCase


class FunctionTests(SimpleTestCase):
    def test_values(self):
        """
        Tests the get_digit function to extract digits from a given number at various positions. 

        The function validates the correctness of the get_digit function by comparing its output with expected values for different input positions, ensuring it behaves correctly for positions within and beyond the number of digits in the input number.
        """
        self.assertEqual(get_digit(123, 1), 3)
        self.assertEqual(get_digit(123, 2), 2)
        self.assertEqual(get_digit(123, 3), 1)
        self.assertEqual(get_digit(123, 4), 0)
        self.assertEqual(get_digit(123, 0), 123)

    def test_string(self):
        self.assertEqual(get_digit("xyz", 0), "xyz")
