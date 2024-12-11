from django.test import SimpleTestCase

from ..utils import setup


class TruncatecharsTests(SimpleTestCase):
    @setup({"truncatechars01": "{{ a|truncatechars:3 }}"})
    def test_truncatechars01(self):
        output = self.engine.render_to_string(
            "truncatechars01", {"a": "Testing, testing"}
        )
        self.assertEqual(output, "Te…")

    @setup({"truncatechars02": "{{ a|truncatechars:7 }}"})
    def test_truncatechars02(self):
        """
        Test the truncatechars filter, ensuring it correctly truncates a string to the specified length.

        The filter is expected to limit the input string to a maximum of 7 characters. 
        In cases where the input string is shorter than or equal to the specified length, 
        the original string should be returned unchanged.

        This test verifies that the filter behaves as expected, 
        returning the input string 'Testing' unchanged since its length is less than or equal to 7 characters.
        """
        output = self.engine.render_to_string("truncatechars02", {"a": "Testing"})
        self.assertEqual(output, "Testing")

    @setup({"truncatechars03": "{{ a|truncatechars:'e' }}"})
    def test_fail_silently_incorrect_arg(self):
        """
        Tests the failure handling of the truncatechars filter when provided with an invalid argument.

        This function verifies that the filter correctly handles an incorrect argument by checking if the output remains unchanged.

        The test case checks for the 'truncatechars' filter being passed an argument that is not an integer, in this case 'e'. The expected output should be the original string 'Testing, testing', indicating that the filter failed silently and did not modify the string.

        The purpose of this test is to ensure that the truncatechars filter behaves predictably and does not raise exceptions when passed invalid arguments, rather it defaults to leaving the string unmodified.
        """
        output = self.engine.render_to_string(
            "truncatechars03", {"a": "Testing, testing"}
        )
        self.assertEqual(output, "Testing, testing")

    @setup({"truncatechars04": "{{ a|truncatechars:3 }}"})
    def test_truncatechars04(self):
        output = self.engine.render_to_string("truncatechars04", {"a": "abc"})
        self.assertEqual(output, "abc")
