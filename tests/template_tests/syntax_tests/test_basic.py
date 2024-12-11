from django.template.base import TemplateSyntaxError
from django.template.context import Context
from django.template.loader_tags import BlockContext, BlockNode
from django.test import SimpleTestCase

from ..utils import SilentAttrClass, SilentGetItemClass, SomeClass, setup

basic_templates = {
    "basic-syntax01": "something cool",
    "basic-syntax02": "{{ headline }}",
    "basic-syntax03": "{{ first }} --- {{ second }}",
}


class BasicSyntaxTests(SimpleTestCase):
    @setup(basic_templates)
    def test_basic_syntax01(self):
        """
        Plain text should go through the template parser untouched.
        """
        output = self.engine.render_to_string("basic-syntax01")
        self.assertEqual(output, "something cool")

    @setup(basic_templates)
    def test_basic_syntax02(self):
        """
        Variables should be replaced with their value in the current
        context
        """
        output = self.engine.render_to_string("basic-syntax02", {"headline": "Success"})
        self.assertEqual(output, "Success")

    @setup(basic_templates)
    def test_basic_syntax03(self):
        """
        More than one replacement variable is allowed in a template
        """
        output = self.engine.render_to_string(
            "basic-syntax03", {"first": 1, "second": 2}
        )
        self.assertEqual(output, "1 --- 2")

    @setup({"basic-syntax04": "as{{ missing }}df"})
    def test_basic_syntax04(self):
        """
        Fail silently when a variable is not found in the current context
        """
        output = self.engine.render_to_string("basic-syntax04")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "asINVALIDdf")
        else:
            self.assertEqual(output, "asdf")

    @setup({"basic-syntax06": "{{ multi word variable }}"})
    def test_basic_syntax06(self):
        """
        A variable may not contain more than one word
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax06")

    @setup({"basic-syntax07": "{{ }}"})
    def test_basic_syntax07(self):
        """
        Raise TemplateSyntaxError for empty variable tags.
        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "Empty variable tag on line 1"
        ):
            self.engine.get_template("basic-syntax07")

    @setup({"basic-syntax08": "{{        }}"})
    def test_basic_syntax08(self):
        """
        Raise TemplateSyntaxError for empty variable tags.
        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "Empty variable tag on line 1"
        ):
            self.engine.get_template("basic-syntax08")

    @setup({"basic-syntax09": "{{ var.method }}"})
    def test_basic_syntax09(self):
        """
        Attribute syntax allows a template to call an object's attribute
        """
        output = self.engine.render_to_string("basic-syntax09", {"var": SomeClass()})
        self.assertEqual(output, "SomeClass.method")

    @setup({"basic-syntax10": "{{ var.otherclass.method }}"})
    def test_basic_syntax10(self):
        """
        Multiple levels of attribute access are allowed.
        """
        output = self.engine.render_to_string("basic-syntax10", {"var": SomeClass()})
        self.assertEqual(output, "OtherClass.method")

    @setup({"basic-syntax11": "{{ var.blech }}"})
    def test_basic_syntax11(self):
        """
        Fail silently when a variable's attribute isn't found.
        """
        output = self.engine.render_to_string("basic-syntax11", {"var": SomeClass()})

        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"basic-syntax12": "{{ var.__dict__ }}"})
    def test_basic_syntax12(self):
        """
        Raise TemplateSyntaxError when trying to access a variable
        beginning with an underscore.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax12")

    # Raise TemplateSyntaxError when trying to access a variable
    # containing an illegal character.
    @setup({"basic-syntax13": "{{ va>r }}"})
    def test_basic_syntax13(self):
        """
        Tests the basic syntax of a templating engine to ensure it correctly raises a TemplateSyntaxError when encountering invalid syntax, specifically an undefined variable access operation.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax13")

    @setup({"basic-syntax14": "{{ (var.r) }}"})
    def test_basic_syntax14(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax14")

    @setup({"basic-syntax15": "{{ sp%am }}"})
    def test_basic_syntax15(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax15")

    @setup({"basic-syntax16": "{{ eggs! }}"})
    def test_basic_syntax16(self):
        """
        Tests that using an exclamation mark after a variable in a template raises a TemplateSyntaxError.

        This test case ensures that the template engine correctly handles invalid syntax
        and raises an exception when it encounters an unexpected character after a variable.
        The test verifies that the engine's parsing logic is working as expected and that
        it provides a clear error message when encountering invalid template syntax.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax16")

    @setup({"basic-syntax17": "{{ moo? }}"})
    def test_basic_syntax17(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax17")

    @setup({"basic-syntax18": "{{ foo.bar }}"})
    def test_basic_syntax18(self):
        """
        Attribute syntax allows a template to call a dictionary key's
        value.
        """
        output = self.engine.render_to_string("basic-syntax18", {"foo": {"bar": "baz"}})
        self.assertEqual(output, "baz")

    @setup({"basic-syntax19": "{{ foo.spam }}"})
    def test_basic_syntax19(self):
        """
        Fail silently when a variable's dictionary key isn't found.
        """
        output = self.engine.render_to_string("basic-syntax19", {"foo": {"bar": "baz"}})

        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"basic-syntax20": "{{ var.method2 }}"})
    def test_basic_syntax20(self):
        """
        Fail silently when accessing a non-simple method
        """
        output = self.engine.render_to_string("basic-syntax20", {"var": SomeClass()})

        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"basic-syntax20b": "{{ var.method5 }}"})
    def test_basic_syntax20b(self):
        """
        Don't silence a TypeError if it was raised inside a callable.
        """
        template = self.engine.get_template("basic-syntax20b")

        with self.assertRaises(TypeError):
            template.render(Context({"var": SomeClass()}))

    # Don't get confused when parsing something that is almost, but not
    # quite, a template tag.
    @setup({"basic-syntax21": "a {{ moo %} b"})
    def test_basic_syntax21(self):
        output = self.engine.render_to_string("basic-syntax21")
        self.assertEqual(output, "a {{ moo %} b")

    @setup({"basic-syntax22": "{{ moo #}"})
    def test_basic_syntax22(self):
        """

        Tests the rendering of a basic syntax template string containing an opening brace and a hash character.

        The purpose of this test is to verify that the templating engine correctly handles a specific edge case where the template string contains 
        an opening brace '{{' followed by a hash character '#', without interpreting it as a special syntax or command. 

        The expected output is the original template string, unchanged, confirming that the engine does not attempt to parse or evaluate the 
        sequence as a template directive.

        """
        output = self.engine.render_to_string("basic-syntax22")
        self.assertEqual(output, "{{ moo #}")

    @setup({"basic-syntax23": "{{ moo #} {{ cow }}"})
    def test_basic_syntax23(self):
        """
        Treat "moo #} {{ cow" as the variable. Not ideal, but costly to work
        around, so this triggers an error.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax23")

    @setup({"basic-syntax24": "{{ moo\n }}"})
    def test_basic_syntax24(self):
        """
        Embedded newlines make it not-a-tag.
        """
        output = self.engine.render_to_string("basic-syntax24")
        self.assertEqual(output, "{{ moo\n }}")

    # Literal strings are permitted inside variables, mostly for i18n
    # purposes.
    @setup({"basic-syntax25": '{{ "fred" }}'})
    def test_basic_syntax25(self):
        """

        Test rendering of basic syntax in a template engine.

        This test case verifies that the template engine correctly renders a simple template
        with a variable substitution. It checks that the engine replaces the variable with
        its actual value and produces the expected output.

        """
        output = self.engine.render_to_string("basic-syntax25")
        self.assertEqual(output, "fred")

    @setup({"basic-syntax26": r'{{ "\"fred\"" }}'})
    def test_basic_syntax26(self):
        """

        Tests the rendering of a template with a basic syntax escaped double quote.

        Verifies that the engine correctly renders the template and unescapes the double quote,
        producing the expected output string.

        """
        output = self.engine.render_to_string("basic-syntax26")
        self.assertEqual(output, '"fred"')

    @setup({"basic-syntax27": r'{{ _("\"fred\"") }}'})
    def test_basic_syntax27(self):
        """
        Test the basic syntax of the template engine for rendering escaped backslashes.

        This test case verifies that the engine correctly handles backslash escaping,
        ensuring that the output matches the expected string literal. It checks if the
        rendered template produces a string with properly escaped backslashes, which is
        essential for accurate representation of string literals in the output.

        The test renders a template containing a double backslash and compares the result
        with the expected output, validating the engine's syntax handling capabilities.
        """
        output = self.engine.render_to_string("basic-syntax27")
        self.assertEqual(output, '"fred"')

    # #12554 -- Make sure a silent_variable_failure Exception is
    # suppressed on dictionary and attribute lookup.
    @setup({"basic-syntax28": "{{ a.b }}"})
    def test_basic_syntax28(self):
        """
        Tests the rendering of dot notation in a template string when the attribute does not exist and SilentGetItemClass is used.

            The test confirms whether the rendering engine correctly handles the case when the attribute 'b' of object 'a' is accessed, 
            but does not exist, and whether it outputs the correct result based on the 'string_if_invalid' setting of the engine.
        """
        output = self.engine.render_to_string(
            "basic-syntax28", {"a": SilentGetItemClass()}
        )
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"basic-syntax29": "{{ a.b }}"})
    def test_basic_syntax29(self):
        """
        Test a basic syntax case where a nested attribute 'b' is accessed on an object 'a' using the dot notation. 

        This function checks how the templating engine handles the rendering of a template containing an undefined attribute. 

        It renders a template with the given syntax and checks if the output is either an 'INVALID' string or an empty string, depending on the engine's configuration for handling invalid syntax.
        """
        output = self.engine.render_to_string(
            "basic-syntax29", {"a": SilentAttrClass()}
        )
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    # Something that starts like a number but has an extra lookup works
    # as a lookup.
    @setup({"basic-syntax30": "{{ 1.2.3 }}"})
    def test_basic_syntax30(self):
        output = self.engine.render_to_string(
            "basic-syntax30", {"1": {"2": {"3": "d"}}}
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax31": "{{ 1.2.3 }}"})
    def test_basic_syntax31(self):
        """
        Tests rendering of a basic syntax template with nested dictionary access, verifying that the engine correctly retrieves the last element from a tuple within a nested dictionary structure.
        """
        output = self.engine.render_to_string(
            "basic-syntax31",
            {"1": {"2": ("a", "b", "c", "d")}},
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax32": "{{ 1.2.3 }}"})
    def test_basic_syntax32(self):
        output = self.engine.render_to_string(
            "basic-syntax32",
            {"1": (("x", "x", "x", "x"), ("y", "y", "y", "y"), ("a", "b", "c", "d"))},
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax33": "{{ 1.2.3 }}"})
    def test_basic_syntax33(self):
        """

        Tests the basic syntax of the templating engine by rendering a template with a nested tuple.

        The test case verifies that the templating engine correctly extracts the last element from the nested tuple.

        :returns: None

        """
        output = self.engine.render_to_string(
            "basic-syntax33",
            {"1": ("xxxx", "yyyy", "abcd")},
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax34": "{{ 1.2.3 }}"})
    def test_basic_syntax34(self):
        """

        Test the rendering of a template with nested objects in the basic syntax 1.2.3.

        This test case verifies that the templating engine can correctly retrieve and render the value
        of a nested object within the template syntax {{ 1.2.3 }} when provided with a dictionary
        containing nested dictionaries and a list of dictionaries.

        """
        output = self.engine.render_to_string(
            "basic-syntax34", {"1": ({"x": "x"}, {"y": "y"}, {"z": "z", "3": "d"})}
        )
        self.assertEqual(output, "d")

    # Numbers are numbers even if their digits are in the context.
    @setup({"basic-syntax35": "{{ 1 }}"})
    def test_basic_syntax35(self):
        output = self.engine.render_to_string("basic-syntax35", {"1": "abc"})
        self.assertEqual(output, "1")

    @setup({"basic-syntax36": "{{ 1.2 }}"})
    def test_basic_syntax36(self):
        output = self.engine.render_to_string("basic-syntax36", {"1": "abc"})
        self.assertEqual(output, "1.2")

    @setup({"basic-syntax37": "{{ callable }}"})
    def test_basic_syntax37(self):
        """
        Call methods in the top level of the context.
        """
        output = self.engine.render_to_string(
            "basic-syntax37", {"callable": lambda: "foo bar"}
        )
        self.assertEqual(output, "foo bar")

    @setup({"basic-syntax38": "{{ var.callable }}"})
    def test_basic_syntax38(self):
        """
        Call methods returned from dictionary lookups.
        """
        output = self.engine.render_to_string(
            "basic-syntax38", {"var": {"callable": lambda: "foo bar"}}
        )
        self.assertEqual(output, "foo bar")

    @setup({"template": "{% block content %}"})
    def test_unclosed_block(self):
        msg = "Unclosed tag on line 1: 'block'. Looking for one of: endblock."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": "{% if a %}"})
    def test_unclosed_block2(self):
        msg = "Unclosed tag on line 1: 'if'. Looking for one of: elif, else, endif."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"tpl-str": "%s", "tpl-percent": "%%", "tpl-weird-percent": "% %s"})
    def test_ignores_strings_that_look_like_format_interpolation(self):
        """
        Tests that the templating engine correctly ignores strings that resemble format interpolation.

        Verifies that the engine treats strings containing percentage signs and other format-like patterns as literal strings,
        rather than attempting to interpolate them. This ensures that the engine ruggedly handles templates containing such patterns,
        yielding the original string as output without modification. 
        """
        output = self.engine.render_to_string("tpl-str")
        self.assertEqual(output, "%s")
        output = self.engine.render_to_string("tpl-percent")
        self.assertEqual(output, "%%")
        output = self.engine.render_to_string("tpl-weird-percent")
        self.assertEqual(output, "% %s")


class BlockContextTests(SimpleTestCase):
    def test_repr(self):
        block_context = BlockContext()
        block_context.add_blocks({"content": BlockNode("content", [])})
        self.assertEqual(
            repr(block_context),
            "<BlockContext: blocks=defaultdict(<class 'list'>, "
            "{'content': [<Block Node: content. Contents: []>]})>",
        )
