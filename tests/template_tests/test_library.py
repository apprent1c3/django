import functools

from django.template import Library
from django.template.base import Node
from django.test import SimpleTestCase


class FilterRegistrationTests(SimpleTestCase):
    def setUp(self):
        """
        This is a comment
        """
        self.library = Library()

    def test_filter(self):
        @self.library.filter
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        self.assertEqual(self.library.filters["func"], func)

    def test_filter_parens(self):
        @self.library.filter()
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        self.assertEqual(self.library.filters["func"], func)

    def test_filter_name_arg(self):
        @self.library.filter("name")
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        self.assertEqual(self.library.filters["name"], func)

    def test_filter_name_kwarg(self):
        @self.library.filter(name="name")
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        self.assertEqual(self.library.filters["name"], func)

    def test_filter_call(self):
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        self.library.filter("name", func)
        self.assertEqual(self.library.filters["name"], func)

    def test_filter_invalid(self):
        """
        This is a comment
        """
        msg = "Unsupported arguments to Library.filter: (None, '')"
        with self.assertRaisesMessage(ValueError, msg):
            self.library.filter(None, "")


class InclusionTagRegistrationTests(SimpleTestCase):
    def setUp(self):
        """
        This is a comment
        """
        self.library = Library()

    def test_inclusion_tag(self):
        @self.library.inclusion_tag("template.html")
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        self.assertIn("func", self.library.tags)

    def test_inclusion_tag_name(self):
        @self.library.inclusion_tag("template.html", name="name")
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        self.assertIn("name", self.library.tags)

    def test_inclusion_tag_wrapped(self):
        @self.library.inclusion_tag("template.html")
        @functools.lru_cache(maxsize=32)
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        func_wrapped = self.library.tags["func"].__wrapped__
        self.assertIs(func_wrapped, func)
        self.assertTrue(hasattr(func_wrapped, "cache_info"))


class SimpleTagRegistrationTests(SimpleTestCase):
    def setUp(self):
        """
        This is a comment
        """
        self.library = Library()

    def test_simple_tag(self):
        @self.library.simple_tag
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        self.assertIn("func", self.library.tags)

    def test_simple_tag_parens(self):
        @self.library.simple_tag()
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        self.assertIn("func", self.library.tags)

    def test_simple_tag_name_kwarg(self):
        @self.library.simple_tag(name="name")
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        self.assertIn("name", self.library.tags)

    def test_simple_tag_invalid(self):
        """
        This is a comment
        """
        msg = "Invalid arguments provided to simple_tag"
        with self.assertRaisesMessage(ValueError, msg):
            self.library.simple_tag("invalid")

    def test_simple_tag_wrapped(self):
        @self.library.simple_tag
        @functools.lru_cache(maxsize=32)
        """
        This is a comment
        """
        def func():
            """
            This is a comment
            """
            return ""

        func_wrapped = self.library.tags["func"].__wrapped__
        self.assertIs(func_wrapped, func)
        self.assertTrue(hasattr(func_wrapped, "cache_info"))


class TagRegistrationTests(SimpleTestCase):
    def setUp(self):
        """
        This is a comment
        """
        self.library = Library()

    def test_tag(self):
        @self.library.tag
        """
        This is a comment
        """
        def func(parser, token):
            """
            This is a comment
            """
            return Node()

        self.assertEqual(self.library.tags["func"], func)

    def test_tag_parens(self):
        @self.library.tag()
        """
        This is a comment
        """
        def func(parser, token):
            """
            This is a comment
            """
            return Node()

        self.assertEqual(self.library.tags["func"], func)

    def test_tag_name_arg(self):
        @self.library.tag("name")
        """
        This is a comment
        """
        def func(parser, token):
            """
            This is a comment
            """
            return Node()

        self.assertEqual(self.library.tags["name"], func)

    def test_tag_name_kwarg(self):
        @self.library.tag(name="name")
        """
        This is a comment
        """
        def func(parser, token):
            """
            This is a comment
            """
            return Node()

        self.assertEqual(self.library.tags["name"], func)

    def test_tag_call(self):
        """
        This is a comment
        """
        def func(parser, token):
            """
            This is a comment
            """
            return Node()

        self.library.tag("name", func)
        self.assertEqual(self.library.tags["name"], func)

    def test_tag_invalid(self):
        """
        This is a comment
        """
        msg = "Unsupported arguments to Library.tag: (None, '')"
        with self.assertRaisesMessage(ValueError, msg):
            self.library.tag(None, "")
