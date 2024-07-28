from django.template.defaultfilters import divisibleby
from django.test import SimpleTestCase


class FunctionTests(SimpleTestCase):
    def test_true(self):
        """
        This is a comment
        """
        self.assertIs(divisibleby(4, 2), True)

    def test_false(self):
        """
        This is a comment
        """
        self.assertIs(divisibleby(4, 3), False)
