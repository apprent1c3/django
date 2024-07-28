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
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax01")
        self.assertEqual(output, "something cool")

    @setup(basic_templates)
    def test_basic_syntax02(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax02", {"headline": "Success"})
        self.assertEqual(output, "Success")

    @setup(basic_templates)
    def test_basic_syntax03(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "basic-syntax03", {"first": 1, "second": 2}
        )
        self.assertEqual(output, "1 --- 2")

    @setup({"basic-syntax04": "as{{ missing }}df"})
    def test_basic_syntax04(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax04")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "asINVALIDdf")
        else:
            self.assertEqual(output, "asdf")

    @setup({"basic-syntax06": "{{ multi word variable }}"})
    def test_basic_syntax06(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax06")

    @setup({"basic-syntax07": "{{ }}"})
    def test_basic_syntax07(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "Empty variable tag on line 1"
        ):
            self.engine.get_template("basic-syntax07")

    @setup({"basic-syntax08": "{{        }}"})
    def test_basic_syntax08(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "Empty variable tag on line 1"
        ):
            self.engine.get_template("basic-syntax08")

    @setup({"basic-syntax09": "{{ var.method }}"})
    def test_basic_syntax09(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax09", {"var": SomeClass()})
        self.assertEqual(output, "SomeClass.method")

    @setup({"basic-syntax10": "{{ var.otherclass.method }}"})
    def test_basic_syntax10(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax10", {"var": SomeClass()})
        self.assertEqual(output, "OtherClass.method")

    @setup({"basic-syntax11": "{{ var.blech }}"})
    def test_basic_syntax11(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax11", {"var": SomeClass()})

        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"basic-syntax12": "{{ var.__dict__ }}"})
    def test_basic_syntax12(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax12")

    # Raise TemplateSyntaxError when trying to access a variable
    # containing an illegal character.
    @setup({"basic-syntax13": "{{ va>r }}"})
    def test_basic_syntax13(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax13")

    @setup({"basic-syntax14": "{{ (var.r) }}"})
    def test_basic_syntax14(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax14")

    @setup({"basic-syntax15": "{{ sp%am }}"})
    def test_basic_syntax15(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax15")

    @setup({"basic-syntax16": "{{ eggs! }}"})
    def test_basic_syntax16(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax16")

    @setup({"basic-syntax17": "{{ moo? }}"})
    def test_basic_syntax17(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax17")

    @setup({"basic-syntax18": "{{ foo.bar }}"})
    def test_basic_syntax18(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax18", {"foo": {"bar": "baz"}})
        self.assertEqual(output, "baz")

    @setup({"basic-syntax19": "{{ foo.spam }}"})
    def test_basic_syntax19(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax19", {"foo": {"bar": "baz"}})

        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"basic-syntax20": "{{ var.method2 }}"})
    def test_basic_syntax20(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax20", {"var": SomeClass()})

        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"basic-syntax20b": "{{ var.method5 }}"})
    def test_basic_syntax20b(self):
        """
        This is a comment
        """
        template = self.engine.get_template("basic-syntax20b")

        with self.assertRaises(TypeError):
            template.render(Context({"var": SomeClass()}))

    # Don't get confused when parsing something that is almost, but not
    # quite, a template tag.
    @setup({"basic-syntax21": "a {{ moo %} b"})
    def test_basic_syntax21(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax21")
        self.assertEqual(output, "a {{ moo %} b")

    @setup({"basic-syntax22": "{{ moo #}"})
    def test_basic_syntax22(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax22")
        self.assertEqual(output, "{{ moo #}")

    @setup({"basic-syntax23": "{{ moo #} {{ cow }}"})
    def test_basic_syntax23(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("basic-syntax23")

    @setup({"basic-syntax24": "{{ moo\n }}"})
    def test_basic_syntax24(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax24")
        self.assertEqual(output, "{{ moo\n }}")

    # Literal strings are permitted inside variables, mostly for i18n
    # purposes.
    @setup({"basic-syntax25": '{{ "fred" }}'})
    def test_basic_syntax25(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax25")
        self.assertEqual(output, "fred")

    @setup({"basic-syntax26": r'{{ "\"fred\"" }}'})
    def test_basic_syntax26(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax26")
        self.assertEqual(output, '"fred"')

    @setup({"basic-syntax27": r'{{ _("\"fred\"") }}'})
    def test_basic_syntax27(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax27")
        self.assertEqual(output, '"fred"')

    # #12554 -- Make sure a silent_variable_failure Exception is
    # suppressed on dictionary and attribute lookup.
    @setup({"basic-syntax28": "{{ a.b }}"})
    def test_basic_syntax28(self):
        """
        This is a comment
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
        This is a comment
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
        This is a comment
        """
        output = self.engine.render_to_string(
            "basic-syntax30", {"1": {"2": {"3": "d"}}}
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax31": "{{ 1.2.3 }}"})
    def test_basic_syntax31(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "basic-syntax31",
            {"1": {"2": ("a", "b", "c", "d")}},
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax32": "{{ 1.2.3 }}"})
    def test_basic_syntax32(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "basic-syntax32",
            {"1": (("x", "x", "x", "x"), ("y", "y", "y", "y"), ("a", "b", "c", "d"))},
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax33": "{{ 1.2.3 }}"})
    def test_basic_syntax33(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "basic-syntax33",
            {"1": ("xxxx", "yyyy", "abcd")},
        )
        self.assertEqual(output, "d")

    @setup({"basic-syntax34": "{{ 1.2.3 }}"})
    def test_basic_syntax34(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "basic-syntax34", {"1": ({"x": "x"}, {"y": "y"}, {"z": "z", "3": "d"})}
        )
        self.assertEqual(output, "d")

    # Numbers are numbers even if their digits are in the context.
    @setup({"basic-syntax35": "{{ 1 }}"})
    def test_basic_syntax35(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax35", {"1": "abc"})
        self.assertEqual(output, "1")

    @setup({"basic-syntax36": "{{ 1.2 }}"})
    def test_basic_syntax36(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("basic-syntax36", {"1": "abc"})
        self.assertEqual(output, "1.2")

    @setup({"basic-syntax37": "{{ callable }}"})
    def test_basic_syntax37(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "basic-syntax37", {"callable": lambda: "foo bar"}
        )
        self.assertEqual(output, "foo bar")

    @setup({"basic-syntax38": "{{ var.callable }}"})
    def test_basic_syntax38(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "basic-syntax38", {"var": {"callable": lambda: "foo bar"}}
        )
        self.assertEqual(output, "foo bar")

    @setup({"template": "{% block content %}"})
    def test_unclosed_block(self):
        """
        This is a comment
        """
        msg = "Unclosed tag on line 1: 'block'. Looking for one of: endblock."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": "{% if a %}"})
    def test_unclosed_block2(self):
        """
        This is a comment
        """
        msg = "Unclosed tag on line 1: 'if'. Looking for one of: elif, else, endif."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"tpl-str": "%s", "tpl-percent": "%%", "tpl-weird-percent": "% %s"})
    def test_ignores_strings_that_look_like_format_interpolation(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("tpl-str")
        self.assertEqual(output, "%s")
        output = self.engine.render_to_string("tpl-percent")
        self.assertEqual(output, "%%")
        output = self.engine.render_to_string("tpl-weird-percent")
        self.assertEqual(output, "% %s")


class BlockContextTests(SimpleTestCase):
    def test_repr(self):
        """
        This is a comment
        """
        block_context = BlockContext()
        block_context.add_blocks({"content": BlockNode("content", [])})
        self.assertEqual(
            repr(block_context),
            "<BlockContext: blocks=defaultdict(<class 'list'>, "
            "{'content': [<Block Node: content. Contents: []>]})>",
        )
