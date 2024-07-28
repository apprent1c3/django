from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class WidthRatioTagTests(SimpleTestCase):
    libraries = {"custom": "template_tests.templatetags.custom"}

    @setup({"widthratio01": "{% widthratio a b 0 %}"})
    def test_widthratio01(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio01", {"a": 50, "b": 100})
        self.assertEqual(output, "0")

    @setup({"widthratio02": "{% widthratio a b 100 %}"})
    def test_widthratio02(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio02", {"a": 0, "b": 0})
        self.assertEqual(output, "0")

    @setup({"widthratio03": "{% widthratio a b 100 %}"})
    def test_widthratio03(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio03", {"a": 0, "b": 100})
        self.assertEqual(output, "0")

    @setup({"widthratio04": "{% widthratio a b 100 %}"})
    def test_widthratio04(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio04", {"a": 50, "b": 100})
        self.assertEqual(output, "50")

    @setup({"widthratio05": "{% widthratio a b 100 %}"})
    def test_widthratio05(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio05", {"a": 100, "b": 100})
        self.assertEqual(output, "100")

    @setup({"widthratio06": "{% widthratio a b 100 %}"})
    def test_widthratio06(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio06", {"a": 50, "b": 80})
        self.assertEqual(output, "62")

    @setup({"widthratio07": "{% widthratio a b 100 %}"})
    def test_widthratio07(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio07", {"a": 50, "b": 70})
        self.assertEqual(output, "71")

    # Raise exception if we don't have 3 args, last one an integer
    @setup({"widthratio08": "{% widthratio %}"})
    def test_widthratio08(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("widthratio08")

    @setup({"widthratio09": "{% widthratio a b %}"})
    def test_widthratio09(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("widthratio09", {"a": 50, "b": 100})

    @setup({"widthratio10": "{% widthratio a b 100.0 %}"})
    def test_widthratio10(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio10", {"a": 50, "b": 100})
        self.assertEqual(output, "50")

    @setup({"widthratio11": "{% widthratio a b c %}"})
    def test_widthratio11(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "widthratio11", {"a": 50, "c": 100, "b": 100}
        )
        self.assertEqual(output, "50")

    # #18739: widthratio should handle None args consistently with
    # non-numerics
    @setup({"widthratio12a": "{% widthratio a b c %}"})
    def test_widthratio12a(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "widthratio12a", {"a": "a", "c": 100, "b": 100}
        )
        self.assertEqual(output, "")

    @setup({"widthratio12b": "{% widthratio a b c %}"})
    def test_widthratio12b(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "widthratio12b", {"a": None, "c": 100, "b": 100}
        )
        self.assertEqual(output, "")

    @setup({"widthratio13a": "{% widthratio a b c %}"})
    def test_widthratio13a(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "widthratio13a", {"a": 0, "c": 100, "b": "b"}
        )
        self.assertEqual(output, "")

    @setup({"widthratio13b": "{% widthratio a b c %}"})
    def test_widthratio13b(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "widthratio13b", {"a": 0, "c": 100, "b": None}
        )
        self.assertEqual(output, "")

    @setup({"widthratio14a": "{% widthratio a b c %}"})
    def test_widthratio14a(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("widthratio14a", {"a": 0, "c": "c", "b": 100})

    @setup({"widthratio14b": "{% widthratio a b c %}"})
    def test_widthratio14b(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("widthratio14b", {"a": 0, "c": None, "b": 100})

    @setup({"widthratio15": '{% load custom %}{% widthratio a|noop:"x y" b 0 %}'})
    def test_widthratio15(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio15", {"a": 50, "b": 100})
        self.assertEqual(output, "0")

    # Widthratio with variable assignment
    @setup({"widthratio16": "{% widthratio a b 100 as variable %}-{{ variable }}-"})
    def test_widthratio16(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio16", {"a": 50, "b": 100})
        self.assertEqual(output, "-50-")

    @setup({"widthratio17": "{% widthratio a b 100 as variable %}-{{ variable }}-"})
    def test_widthratio17(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("widthratio17", {"a": 100, "b": 100})
        self.assertEqual(output, "-100-")

    @setup({"widthratio18": "{% widthratio a b 100 as %}"})
    def test_widthratio18(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("widthratio18")

    @setup({"widthratio19": "{% widthratio a b 100 not_as variable %}"})
    def test_widthratio19(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("widthratio19")

    @setup({"widthratio20": "{% widthratio a b 100 %}"})
    def test_widthratio20(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "widthratio20", {"a": float("inf"), "b": float("inf")}
        )
        self.assertEqual(output, "")

    @setup({"widthratio21": "{% widthratio a b 100 %}"})
    def test_widthratio21(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "widthratio21", {"a": float("inf"), "b": 2}
        )
        self.assertEqual(output, "")

    @setup({"t": "{% widthratio a b 100 as variable %}-{{ variable }}-"})
    def test_zerodivisionerror_as_var(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("t", {"a": 0, "b": 0})
        self.assertEqual(output, "-0-")

    @setup({"t": "{% widthratio a b c as variable %}-{{ variable }}-"})
    def test_typeerror_as_var(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("t", {"a": "a", "c": 100, "b": 100})
        self.assertEqual(output, "--")
