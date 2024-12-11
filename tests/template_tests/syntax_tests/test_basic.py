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
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax13")

    @setup({"basic-syntax14": "{{ (var.r) }}"})
    def test_basic_syntax14(self):
        """

        Tests that the template engine correctly raises a TemplateSyntaxError when encountering 
        invalid syntax, specifically a lone closing parenthesis in a template.

        The test verifies that an error is raised when the template contains a syntax error,
        ensuring that the engine properly handles malformed templates and provides informative 
        error messages instead of producing unexpected results.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax14")

    @setup({"basic-syntax15": "{{ sp%am }}"})
    def test_basic_syntax15(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax15")

    @setup({"basic-syntax16": "{{ eggs! }}"})
    def test_basic_syntax16(self):
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
        """
        Tests the rendering of a template containing basic syntax with comments and expressions.

        This function verifies that the template engine correctly handles a template with
        a comment and an expression, ensuring that the output is rendered as expected.
        The test checks that the rendered string matches the original template, 
        indicating that no modifications were made during the rendering process.
        """
        output = self.engine.render_to_string("basic-syntax21")
        self.assertEqual(output, "a {{ moo %} b")

    @setup({"basic-syntax22": "{{ moo #}"})
    def test_basic_syntax22(self):
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

        Tests the basic syntax for template rendering.

        This test case verifies that the engine correctly replaces a template variable
        with its corresponding value, resulting in the expected output string.

        """
        output = self.engine.render_to_string("basic-syntax25")
        self.assertEqual(output, "fred")

    @setup({"basic-syntax26": r'{{ "\"fred\"" }}'})
    def test_basic_syntax26(self):
        output = self.engine.render_to_string("basic-syntax26")
        self.assertEqual(output, '"fred"')

    @setup({"basic-syntax27": r'{{ _("\"fred\"") }}'})
    def test_basic_syntax27(self):
        output = self.engine.render_to_string("basic-syntax27")
        self.assertEqual(output, '"fred"')

    # #12554 -- Make sure a silent_variable_failure Exception is
    # suppressed on dictionary and attribute lookup.
    @setup({"basic-syntax28": "{{ a.b }}"})
    def test_basic_syntax28(self):
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

        Tests the basic syntax for rendering a dot notation attribute.

        This test case verifies that the templating engine correctly handles the rendering of a dot notation attribute (e.g., 'a.b') when the attribute 'b' does not exist in object 'a'. The expected output is either 'INVALID' if the engine is configured to display an error message for invalid attributes or an empty string if it is configured to silently ignore them.

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
        """

        Tests the basic syntax of nested dictionary access in templating engine.

        This test case verifies that the templating engine correctly renders a nested dictionary
        by accessing a deeply nested value using the dot notation.

        """
        output = self.engine.render_to_string(
            "basic-syntax30", {"1": {"2": {"3": "d"}}}
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax31": "{{ 1.2.3 }}"})
    def test_basic_syntax31(self):
        output = self.engine.render_to_string(
            "basic-syntax31",
            {"1": {"2": ("a", "b", "c", "d")}},
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax32": "{{ 1.2.3 }}"})
    def test_basic_syntax32(self):
        """

        Tests the rendering of a templating engine's basic syntax with nested tuples.

        This test case evaluates the engine's ability to render a template that contains
        a nested tuple structure, verifying that it correctly extracts the last element
        from the nested tuple and renders it as a string. The expected output is a single
        character, demonstrating that the engine properly navigates the nested tuple
        and renders the desired value.

        """
        output = self.engine.render_to_string(
            "basic-syntax32",
            {"1": (("x", "x", "x", "x"), ("y", "y", "y", "y"), ("a", "b", "c", "d"))},
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax33": "{{ 1.2.3 }}"})
    def test_basic_syntax33(self):
        """

        Tests the basic syntax of the templating engine, specifically the syntax for accessing nested objects.

        This test case renders a template with the syntax '{{ 1.2.3 }}' and provides a dictionary with a nested object as input.
        The expected output is the value of the nested object at the specified path.

        It verifies that the engine correctly parses the syntax and retrieves the desired value from the nested object.

        """
        output = self.engine.render_to_string(
            "basic-syntax33",
            {"1": ("xxxx", "yyyy", "abcd")},
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax34": "{{ 1.2.3 }}"})
    def test_basic_syntax34(self):
        """

        Tests the basic syntax of the templating engine, specifically the handling of nested dictionaries and keys.

        The function verifies that the engine correctly renders a template with a nested dictionary structure, 
        using a specific key to access the desired value.

        It checks that the rendered output matches the expected result, ensuring that the engine's syntax 
        is working as expected.

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
        """
        Tests the basic syntax for rendering a template with a numeric literal embedded within a string. 
        Verifies that the rendering engine correctly interprets and represents the numeric literal as part of the output string, rather than attempting to replace it with a variable.
        """
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
        """

        Tests the rendering of a template with an unclosed block tag.

        This function checks that the template engine correctly raises a TemplateSyntaxError when
        a block tag is not closed. It verifies that the error message contains the expected
        information, including the line number and the name of the unclosed tag.

        The purpose of this test is to ensure that the template engine provides useful and accurate
        error messages when encountering syntax errors in templates.

        """
        msg = "Unclosed tag on line 1: 'block'. Looking for one of: endblock."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": "{% if a %}"})
    def test_unclosed_block2(self):
        """
        Tests that the template engine correctly raises a TemplateSyntaxError when an if block is not properly closed. The test verifies that the error message includes the line number and the specific tag that was not closed.
        """
        msg = "Unclosed tag on line 1: 'if'. Looking for one of: elif, else, endif."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"tpl-str": "%s", "tpl-percent": "%%", "tpl-weird-percent": "% %s"})
    def test_ignores_strings_that_look_like_format_interpolation(self):
        output = self.engine.render_to_string("tpl-str")
        self.assertEqual(output, "%s")
        output = self.engine.render_to_string("tpl-percent")
        self.assertEqual(output, "%%")
        output = self.engine.render_to_string("tpl-weird-percent")
        self.assertEqual(output, "% %s")


class BlockContextTests(SimpleTestCase):
    def test_repr(self):
        """
        ..: Tests the representation of a BlockContext object as a string.

            Verifies that the repr function of BlockContext returns the expected string
            representation, including the dictionary of blocks and their corresponding BlockNode
            instances. This ensures that the object can be properly represented and debugged.
        """
        block_context = BlockContext()
        block_context.add_blocks({"content": BlockNode("content", [])})
        self.assertEqual(
            repr(block_context),
            "<BlockContext: blocks=defaultdict(<class 'list'>, "
            "{'content': [<Block Node: content. Contents: []>]})>",
        )
