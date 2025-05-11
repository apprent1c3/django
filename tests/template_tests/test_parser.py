"""
Testing some internals of the template processing.
These are *not* examples to be copied in user code.
"""

from django.template import Library, TemplateSyntaxError
from django.template.base import (
    FilterExpression,
    Lexer,
    Parser,
    Token,
    TokenType,
    Variable,
)
from django.template.defaultfilters import register as filter_library
from django.test import SimpleTestCase


class ParserTests(SimpleTestCase):
    def test_token_smart_split(self):
        """
        #7027 -- _() syntax should work with spaces
        """
        token = Token(
            TokenType.BLOCK, 'sometag _("Page not found") value|yesno:_("yes,no")'
        )
        split = token.split_contents()
        self.assertEqual(
            split, ["sometag", '_("Page not found")', 'value|yesno:_("yes,no")']
        )

    def test_repr(self):
        """

        Tests the string representation of various objects, including Token, Parser, FilterExpression, and Lexer.
        Verifies that each object's repr method returns a string that accurately reflects its contents and state.

        """
        token = Token(TokenType.BLOCK, "some text")
        self.assertEqual(repr(token), '<Block token: "some text...">')
        parser = Parser([token], builtins=[filter_library])
        self.assertEqual(
            repr(parser),
            '<Parser tokens=[<Block token: "some text...">]>',
        )
        filter_expression = FilterExpression("news|upper", parser)
        self.assertEqual(repr(filter_expression), "<FilterExpression 'news|upper'>")
        lexer = Lexer("{% for i in 1 %}{{ a }}\n{% endfor %}")
        self.assertEqual(
            repr(lexer),
            '<Lexer template_string="{% for i in 1 %}{{ a...", verbatim=False>',
        )

    def test_filter_parsing(self):
        """

        Tests the parsing functionality of filter expressions.

        Verifies that filter expressions are correctly evaluated and filters are applied,
        and that variables and attributes are properly handled, including quoted strings
        and escaped characters. Also checks for invalid syntax, such as variables and
        attributes beginning with underscores, and ensures that the correct error messages
        are raised.

        """
        c = {"article": {"section": "News"}}
        p = Parser("", builtins=[filter_library])

        def fe_test(s, val):
            self.assertEqual(FilterExpression(s, p).resolve(c), val)

        fe_test("article.section", "News")
        fe_test("article.section|upper", "NEWS")
        fe_test('"News"', "News")
        fe_test("'News'", "News")
        fe_test(r'"Some \"Good\" News"', 'Some "Good" News')
        fe_test(r'"Some \"Good\" News"', 'Some "Good" News')
        fe_test(r"'Some \'Bad\' News'", "Some 'Bad' News")

        fe = FilterExpression(r'"Some \"Good\" News"', p)
        self.assertEqual(fe.filters, [])
        self.assertEqual(fe.var, 'Some "Good" News')

        # Filtered variables should reject access of attributes beginning with
        # underscores.
        msg = (
            "Variables and attributes may not begin with underscores: 'article._hidden'"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            FilterExpression("article._hidden|upper", p)

    def test_variable_parsing(self):
        """

        Tests the parsing and resolution of variables.

        Ensures correct handling of string literals, dotted notation, and translation markers.
        Also verifies that invalid variable names and non-string inputs raise appropriate errors.

        """
        c = {"article": {"section": "News"}}
        self.assertEqual(Variable("article.section").resolve(c), "News")
        self.assertEqual(Variable('"News"').resolve(c), "News")
        self.assertEqual(Variable("'News'").resolve(c), "News")

        # Translated strings are handled correctly.
        self.assertEqual(Variable("_(article.section)").resolve(c), "News")
        self.assertEqual(Variable('_("Good News")').resolve(c), "Good News")
        self.assertEqual(Variable("_('Better News')").resolve(c), "Better News")

        # Escaped quotes work correctly as well.
        self.assertEqual(
            Variable(r'"Some \"Good\" News"').resolve(c), 'Some "Good" News'
        )
        self.assertEqual(
            Variable(r"'Some \'Better\' News'").resolve(c), "Some 'Better' News"
        )

        # Variables should reject access of attributes and variables beginning
        # with underscores.
        for name in ["article._hidden", "_article"]:
            msg = f"Variables and attributes may not begin with underscores: '{name}'"
            with self.assertRaisesMessage(TemplateSyntaxError, msg):
                Variable(name)

        # Variables should raise on non string type
        with self.assertRaisesMessage(
            TypeError, "Variable must be a string or number, got <class 'dict'>"
        ):
            Variable({})

    def test_filter_args_count(self):
        """
        Tests that FilterExpression raises a TemplateSyntaxError when given a filter with the wrong number of arguments.
        """
        parser = Parser("")
        register = Library()

        @register.filter
        def no_arguments(value):
            pass

        @register.filter
        def one_argument(value, arg):
            pass

        @register.filter
        def one_opt_argument(value, arg=False):
            pass

        @register.filter
        def two_arguments(value, arg, arg2):
            pass

        @register.filter
        def two_one_opt_arg(value, arg, arg2=False):
            pass

        parser.add_library(register)
        for expr in (
            '1|no_arguments:"1"',
            "1|two_arguments",
            '1|two_arguments:"1"',
            "1|two_one_opt_arg",
        ):
            with self.assertRaises(TemplateSyntaxError):
                FilterExpression(expr, parser)
        for expr in (
            # Correct number of arguments
            "1|no_arguments",
            '1|one_argument:"1"',
            # One optional
            "1|one_opt_argument",
            '1|one_opt_argument:"1"',
            # Not supplying all
            '1|two_one_opt_arg:"1"',
        ):
            FilterExpression(expr, parser)
