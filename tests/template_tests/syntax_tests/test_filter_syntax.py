from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import SomeClass, SomeOtherException, UTF8Class, setup


class FilterSyntaxTests(SimpleTestCase):
    @setup({"filter-syntax01": "{{ var|upper }}"})
    def test_filter_syntax01(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "filter-syntax01", {"var": "Django is the greatest!"}
        )
        self.assertEqual(output, "DJANGO IS THE GREATEST!")

    @setup({"filter-syntax02": "{{ var|upper|lower }}"})
    def test_filter_syntax02(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "filter-syntax02", {"var": "Django is the greatest!"}
        )
        self.assertEqual(output, "django is the greatest!")

    @setup({"filter-syntax03": "{{ var |upper }}"})
    def test_filter_syntax03(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "filter-syntax03", {"var": "Django is the greatest!"}
        )
        self.assertEqual(output, "DJANGO IS THE GREATEST!")

    @setup({"filter-syntax04": "{{ var| upper }}"})
    def test_filter_syntax04(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "filter-syntax04", {"var": "Django is the greatest!"}
        )
        self.assertEqual(output, "DJANGO IS THE GREATEST!")

    @setup({"filter-syntax05": "{{ var|does_not_exist }}"})
    def test_filter_syntax05(self):
        """
        This is a comment
        """
        msg = "Invalid filter: 'does_not_exist'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("filter-syntax05")

    @setup({"filter-syntax06": "{{ var|fil(ter) }}"})
    def test_filter_syntax06(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(TemplateSyntaxError, "Invalid filter: 'fil'"):
            self.engine.get_template("filter-syntax06")

    @setup({"filter-syntax07": "{% nothing_to_see_here %}"})
    def test_filter_syntax07(self):
        """
        This is a comment
        """
        msg = (
            "Invalid block tag on line 1: 'nothing_to_see_here'. Did you "
            "forget to register or load this tag?"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("filter-syntax07")

    @setup({"filter-syntax08": "{% %}"})
    def test_filter_syntax08(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(TemplateSyntaxError, "Empty block tag on line 1"):
            self.engine.get_template("filter-syntax08")

    @setup(
        {"filter-syntax08-multi-line": "line 1\nline 2\nline 3{% %}\nline 4\nline 5"}
    )
    def test_filter_syntax08_multi_line(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(TemplateSyntaxError, "Empty block tag on line 3"):
            self.engine.get_template("filter-syntax08-multi-line")

    @setup({"filter-syntax09": '{{ var|cut:"o"|upper|lower }}'})
    def test_filter_syntax09(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("filter-syntax09", {"var": "Foo"})
        self.assertEqual(output, "f")

    @setup({"filter-syntax10": r'{{ var|default_if_none:" endquote\" hah" }}'})
    def test_filter_syntax10(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("filter-syntax10", {"var": None})
        self.assertEqual(output, ' endquote" hah')

    @setup({"filter-syntax11": r"{{ var|default_if_none:var2 }}"})
    def test_filter_syntax11(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "filter-syntax11", {"var": None, "var2": "happy"}
        )
        self.assertEqual(output, "happy")

    @setup({"filter-syntax13": r"1{{ var.method3 }}2"})
    def test_filter_syntax13(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("filter-syntax13", {"var": SomeClass()})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "1INVALID2")
        else:
            self.assertEqual(output, "12")

    @setup({"filter-syntax14": r"1{{ var.method4 }}2"})
    def test_filter_syntax14(self):
        """
        This is a comment
        """
        with self.assertRaises(SomeOtherException):
            self.engine.render_to_string("filter-syntax14", {"var": SomeClass()})

    @setup({"filter-syntax15": r'{{ var|default_if_none:"foo\bar" }}'})
    def test_filter_syntax15(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("filter-syntax15", {"var": None})
        self.assertEqual(output, r"foo\bar")

    @setup({"filter-syntax16": r'{{ var|default_if_none:"foo\now" }}'})
    def test_filter_syntax16(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("filter-syntax16", {"var": None})
        self.assertEqual(output, r"foo\now")

    @setup({"filter-syntax17": r'{{ var|join:"" }}'})
    def test_filter_syntax17(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "filter-syntax17", {"var": ["a", "b", "c"]}
        )
        self.assertEqual(output, "abc")

    @setup({"filter-syntax18": r"{{ var }}"})
    def test_filter_syntax18(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("filter-syntax18", {"var": UTF8Class()})
        self.assertEqual(output, "\u0160\u0110\u0106\u017d\u0107\u017e\u0161\u0111")

    @setup({"filter-syntax19": "{{ var|truncatewords:1 }}"})
    def test_filter_syntax19(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("filter-syntax19", {"var": "hello world"})
        self.assertEqual(output, "hello …")

    @setup({"filter-syntax20": '{{ ""|default_if_none:"was none" }}'})
    def test_filter_syntax20(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("filter-syntax20")
        self.assertEqual(output, "")

    @setup({"filter-syntax21": r"1{{ var.silent_fail_key }}2"})
    def test_filter_syntax21(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("filter-syntax21", {"var": SomeClass()})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "1INVALID2")
        else:
            self.assertEqual(output, "12")

    @setup({"filter-syntax22": r"1{{ var.silent_fail_attribute }}2"})
    def test_filter_syntax22(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("filter-syntax22", {"var": SomeClass()})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "1INVALID2")
        else:
            self.assertEqual(output, "12")

    @setup({"filter-syntax23": r"1{{ var.noisy_fail_key }}2"})
    def test_filter_syntax23(self):
        """
        This is a comment
        """
        with self.assertRaises(SomeOtherException):
            self.engine.render_to_string("filter-syntax23", {"var": SomeClass()})

    @setup({"filter-syntax24": r"1{{ var.noisy_fail_attribute }}2"})
    def test_filter_syntax24(self):
        """
        This is a comment
        """
        with self.assertRaises(SomeOtherException):
            self.engine.render_to_string("filter-syntax24", {"var": SomeClass()})

    @setup({"filter-syntax25": "{{ var.attribute_error_attribute }}"})
    def test_filter_syntax25(self):
        """
        This is a comment
        """
        with self.assertRaises(AttributeError):
            self.engine.render_to_string("filter-syntax25", {"var": SomeClass()})

    @setup({"template": "{{ var.type_error_attribute }}"})
    def test_type_error_attribute(self):
        """
        This is a comment
        """
        with self.assertRaises(TypeError):
            self.engine.render_to_string("template", {"var": SomeClass()})
