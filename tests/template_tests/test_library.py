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

        Tests the filter registration process in the library.

        Verifies that a filter function is successfully registered and stored 
        in the library's filters dictionary under the expected key.

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
        def func():
            return ""

        self.assertEqual(self.library.filters["name"], func)

    def test_filter_call(self):
        def func():
            return ""

        self.library.filter("name", func)
        self.assertEqual(self.library.filters["name"], func)

    def test_filter_invalid(self):
        """

        Tests that the Library.filter method raises a ValueError when given invalid arguments.

        Specifically, this test case checks that passing None and an empty string to the filter method
        results in an error with a meaningful error message, indicating that these arguments are not supported.

        """
        msg = "Unsupported arguments to Library.filter: (None, '')"
        with self.assertRaisesMessage(ValueError, msg):
            self.library.filter(None, "")


class InclusionTagRegistrationTests(SimpleTestCase):
    def setUp(self):
        self.library = Library()

    def test_inclusion_tag(self):
        @self.library.inclusion_tag("template.html")
        """
        Tests the inclusion_tag decorator.

        This test case verifies that a function decorated with the inclusion_tag
        decorator is properly registered in the library's tags. The test creates a
        simple function and decorates it with the inclusion_tag decorator, specifying
        a template file. It then checks that the decorated function is included in
        the library's tags, ensuring that the decorator correctly adds the function
        to the library's namespace.
        """
        def func():
            return ""

        self.assertIn("func", self.library.tags)

    def test_inclusion_tag_name(self):
        @self.library.inclusion_tag("template.html", name="name")
        """

        Test that an inclusion tag is correctly registered with the provided name.

        Verifies that the tag name specified in the decorators is properly added to the library's tags.

        :param none:
        :raises AssertionError: if the tag name is not found in the library's tags.
        :return: None

        """
        def func():
            return ""

        self.assertIn("name", self.library.tags)

    def test_inclusion_tag_wrapped(self):
        @self.library.inclusion_tag("template.html")
        @functools.lru_cache(maxsize=32)
        """
        Tests that when an inclusion tag is wrapped with an LRU cache decorator, 
        the original function is properly preserved and the wrapped function 
        has caching capabilities. Verifies that the wrapped function is 
        identical to the original function and that it has cache information 
        attributes.
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
        """
        Tests the simple_tag decorator by verifying that a decorated function is correctly registered in the library's tags.

        This test case checks if a function decorated with the simple_tag decorator is properly added to the library's tag collection, ensuring that the decorator is working as expected. The test is a basic sanity check for the simple_tag decorator's functionality.
        """
        def func():
            return ""

        self.assertIn("func", self.library.tags)

    def test_simple_tag_parens(self):
        @self.library.simple_tag()
        """
        Tests that a simple tag is registered correctly when using parentheses.

        This test case verifies that a tag function decorated with the simple_tag decorator
        is successfully added to the library's tags dictionary, ensuring it can be used
        in templating operations. The test checks for the presence of the tag function
        name in the library's tags collection, confirming registration occurred as expected.
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
        Tests the registration of a custom tag in the library.

        Verifies that a decorated function is successfully added to the library's tags dictionary.

        The test coverage includes the library's tag decorator functionality and its ability to correctly store the decorated function for later retrieval.

        This test ensures that custom tags can be properly registered and accessed within the library, which is crucial for extending its functionality with user-defined logic.
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
        """
        Tests that a tag function is correctly registered with its name.

        This test case verifies that a tag function is properly associated with its corresponding name in the library's tags dictionary.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the tag function is not correctly registered with its name.

        """
        def func(parser, token):
            return Node()

        self.assertEqual(self.library.tags["name"], func)

    def test_tag_name_kwarg(self):
        @self.library.tag(name="name")
        """

        Tests the assignment of a tag name to a function using the 'name' keyword argument.

        Verifies that the provided function is correctly stored in the library's tags dictionary under the specified name.

        """
        def func(parser, token):
            return Node()

        self.assertEqual(self.library.tags["name"], func)

    def test_tag_call(self):
        """
        Tests that a custom tag can be successfully registered with the library.

        This test case verifies that the tag registration process works as expected,
        by defining a simple tag function and then asserting that it has been correctly
        stored in the library's tags dictionary.

        :param none:
        :returns: None
        :raises: AssertionError if the tag registration fails
        """
        def func(parser, token):
            return Node()

        self.library.tag("name", func)
        self.assertEqual(self.library.tags["name"], func)

    def test_tag_invalid(self):
        """
        Tests that the Library.tag method raises a ValueError when invoked with invalid arguments.

        This test verifies that providing a None value and an empty string as arguments to the tag method results in an exception being raised, ensuring proper validation of input data.

        :raises: ValueError with a message indicating that the provided arguments are unsupported.
        """
        msg = "Unsupported arguments to Library.tag: (None, '')"
        with self.assertRaisesMessage(ValueError, msg):
            self.library.tag(None, "")
