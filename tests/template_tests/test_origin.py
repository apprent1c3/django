import os
from unittest import TestCase

from django.template import Engine

from .utils import TEMPLATE_DIR


class OriginTestCase(TestCase):
    def setUp(self):
        self.engine = Engine(dirs=[TEMPLATE_DIR])

    def test_origin_compares_equal(self):
        a = self.engine.get_template("index.html")
        b = self.engine.get_template("index.html")
        self.assertEqual(a.origin, b.origin)
        # Use assertIs() to test __eq__/__ne__.
        self.assertIs(a.origin == b.origin, True)
        self.assertIs(a.origin != b.origin, False)

    def test_origin_compares_not_equal(self):
        """
        Tests that the origin of two different templates are not equal.

        This test case verifies the expected behavior of the origin comparison for 
        templates retrieved from different locations. It checks that the origin of 
        two templates are not equal, and that the equality and inequality operators 
        return the correct boolean results.

        Checks the following conditions:
        - The origin of two templates from different directories are not equal.
        - The equality comparison (==) of two different origins returns False.
        - The inequality comparison (!=) of two different origins returns True.
        """
        a = self.engine.get_template("first/test.html")
        b = self.engine.get_template("second/test.html")
        self.assertNotEqual(a.origin, b.origin)
        # Use assertIs() to test __eq__/__ne__.
        self.assertIs(a.origin == b.origin, False)
        self.assertIs(a.origin != b.origin, True)

    def test_repr(self):
        """
        Tests the representation of a template origin.

        Verifies that the string representation of a template's origin is correctly formatted,
        including its name. This helps ensure that template origins can be easily identified
        and debugged when needed.

        The test checks if the repr function of a template object returns the expected string
        format, which includes the template's name as a parameter.
        """
        a = self.engine.get_template("index.html")
        name = os.path.join(TEMPLATE_DIR, "index.html")
        self.assertEqual(repr(a.origin), "<Origin name=%r>" % name)
