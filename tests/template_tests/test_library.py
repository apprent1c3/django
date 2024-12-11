import functools

from django.template import Library
from django.template.base import Node
from django.test import SimpleTestCase


class FilterRegistrationTests(SimpleTestCase):
    def setUp(self):
        self.library = Library()

    def test_filter(self):
        @self.library.filter
        """
        Tests the registration of a custom filter with the library.

        Verifies that the filter decorator correctly assigns the filtered function to
        the library's filters dictionary. The test checks if the registered filter function
        is correctly stored and accessible via the library's filters dictionary, ensuring
        that it can be successfully retrieved by its name.

        Args: None
        Returns: None
        """
        def func():
            return ""

        self.assertEqual(self.library.filters["func"], func)

    def test_filter_parens(self):
        @self.library.filter()
        def func():
            return ""

        self.assertEqual(self.library.filters["func"], func)

    def test_filter_name_arg(self):
        @self.library.filter("name")
        def func():
            return ""

        self.assertEqual(self.library.filters["name"], func)

    def test_filter_name_kwarg(self):
        @self.library.filter(name="name")
        """
        Tests that a decorator filter with a specified name is correctly registered in the library.

        The function verifies that when a function is decorated with the library's filter
        decorator and a name is provided as a keyword argument, the decorated function is
        properly stored in the library's filters dictionary under the specified name.

        This ensures that filters can be easily added to the library and retrieved by their
        name, making it convenient to manage and reuse filters throughout the application.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the filter is not correctly registered in the library.
        """
        def func():
            return ""

        self.assertEqual(self.library.filters["name"], func)

    def test_filter_call(self):
        """

        Tests the filter registration functionality of the library.

        This test case checks if a given function can be successfully registered as a filter
        with a specified name, and if the library correctly stores the function for later use.
        The test verifies that the function is successfully added to the library's filters dictionary.

        """
        def func():
            return ""

        self.library.filter("name", func)
        self.assertEqual(self.library.filters["name"], func)

    def test_filter_invalid(self):
        """
        Tests that the Library.filter method raises a ValueError when provided with invalid arguments.

            This test case verifies that the filter function correctly handles None and empty string inputs,
            ensuring that it raises an exception with a meaningful error message when encountering unsupported arguments.

        """
        msg = "Unsupported arguments to Library.filter: (None, '')"
        with self.assertRaisesMessage(ValueError, msg):
            self.library.filter(None, "")


class InclusionTagRegistrationTests(SimpleTestCase):
    def setUp(self):
        self.library = Library()

    def test_inclusion_tag(self):
        @self.library.inclusion_tag("template.html")
        def func():
            return ""

        self.assertIn("func", self.library.tags)

    def test_inclusion_tag_name(self):
        @self.library.inclusion_tag("template.html", name="name")
        def func():
            return ""

        self.assertIn("name", self.library.tags)

    def test_inclusion_tag_wrapped(self):
        @self.library.inclusion_tag("template.html")
        @functools.lru_cache(maxsize=32)
        """
        Checks that an inclusion tag wrapped with a decorator still maintains its original function reference.

        This test verifies that when a function is decorated with :func:`functools.lru_cache` and registered as an inclusion tag, 
        the wrapped function is correctly identified and retains the caching metadata.
        """
        def func():
            return ""

        func_wrapped = self.library.tags["func"].__wrapped__
        self.assertIs(func_wrapped, func)
        self.assertTrue(hasattr(func_wrapped, "cache_info"))


class SimpleTagRegistrationTests(SimpleTestCase):
    def setUp(self):
        self.library = Library()

    def test_simple_tag(self):
        @self.library.simple_tag
        def func():
            return ""

        self.assertIn("func", self.library.tags)

    def test_simple_tag_parens(self):
        @self.library.simple_tag()
        """
        Tests that a simple tag defined with parentheses is correctly registered in the library.

        Verifies that a function decorated with the simple_tag decorator is included in the library's tags.

        """
        def func():
            return ""

        self.assertIn("func", self.library.tags)

    def test_simple_tag_name_kwarg(self):
        @self.library.simple_tag(name="name")
        def func():
            return ""

        self.assertIn("name", self.library.tags)

    def test_simple_tag_invalid(self):
        msg = "Invalid arguments provided to simple_tag"
        with self.assertRaisesMessage(ValueError, msg):
            self.library.simple_tag("invalid")

    def test_simple_tag_wrapped(self):
        @self.library.simple_tag
        @functools.lru_cache(maxsize=32)
        def func():
            return ""

        func_wrapped = self.library.tags["func"].__wrapped__
        self.assertIs(func_wrapped, func)
        self.assertTrue(hasattr(func_wrapped, "cache_info"))


class TagRegistrationTests(SimpleTestCase):
    def setUp(self):
        self.library = Library()

    def test_tag(self):
        @self.library.tag
        """

        Tests the registration of a custom template tag.

        Verifies that a function decorated with the library's tag decorator is correctly
        registered and stored within the library's tags dictionary.

        The test ensures that the decorated function is properly associated with its tag
        name, allowing it to be retrieved and utilized within the template engine.

        """
        def func(parser, token):
            return Node()

        self.assertEqual(self.library.tags["func"], func)

    def test_tag_parens(self):
        @self.library.tag()
        def func(parser, token):
            return Node()

        self.assertEqual(self.library.tags["func"], func)

    def test_tag_name_arg(self):
        @self.library.tag("name")
        def func(parser, token):
            return Node()

        self.assertEqual(self.library.tags["name"], func)

    def test_tag_name_kwarg(self):
        @self.library.tag(name="name")
        """
        Test that the tag name is correctly associated with a function when the name is passed as a keyword argument.
        """
        def func(parser, token):
            return Node()

        self.assertEqual(self.library.tags["name"], func)

    def test_tag_call(self):
        def func(parser, token):
            return Node()

        self.library.tag("name", func)
        self.assertEqual(self.library.tags["name"], func)

    def test_tag_invalid(self):
        """

        Tests that an exception is raised when invalid arguments are passed to the Library.tag method.

        Specifically, it checks that a ValueError is raised when the method is called with a null and empty string argument.

        """
        msg = "Unsupported arguments to Library.tag: (None, '')"
        with self.assertRaisesMessage(ValueError, msg):
            self.library.tag(None, "")
