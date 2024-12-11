import os
from unittest import TestCase

from django.template import Engine

from .utils import TEMPLATE_DIR


class OriginTestCase(TestCase):
    def setUp(self):
        self.engine = Engine(dirs=[TEMPLATE_DIR])

    def test_origin_compares_equal(self):
        """
        Tests that origins of two identical templates are compared as equal.

        This test case verifies that the origin of a template, which represents its source location,
        is correctly compared when two templates with the same name are retrieved from the engine.
        It checks that the equality and inequality comparisons between the origins of these templates
        return the expected boolean results, ensuring that the comparison logic is functioning as expected.
        """
        a = self.engine.get_template("index.html")
        b = self.engine.get_template("index.html")
        self.assertEqual(a.origin, b.origin)
        # Use assertIs() to test __eq__/__ne__.
        self.assertIs(a.origin == b.origin, True)
        self.assertIs(a.origin != b.origin, False)

    def test_origin_compares_not_equal(self):
        """
        Tests that the origin attribute of two different templates compares as not equal.

        Checks that when two templates are loaded from distinct paths, their origin
        attributes do not match, confirming that the origin accurately reflects the
        template's source location. This test verifies the correctness of origin-based
        comparisons using both the ``!=`` operator and the ``==`` operator, ensuring
        that the expected boolean values are returned for unequal origins.
        """
        a = self.engine.get_template("first/test.html")
        b = self.engine.get_template("second/test.html")
        self.assertNotEqual(a.origin, b.origin)
        # Use assertIs() to test __eq__/__ne__.
        self.assertIs(a.origin == b.origin, False)
        self.assertIs(a.origin != b.origin, True)

    def test_repr(self):
        """

        Tests the representation of a template's origin.

        Ensures that the :meth:`repr` method of the template's origin object
        correctly returns a string representation, including the template's name.

        """
        a = self.engine.get_template("index.html")
        name = os.path.join(TEMPLATE_DIR, "index.html")
        self.assertEqual(repr(a.origin), "<Origin name=%r>" % name)
