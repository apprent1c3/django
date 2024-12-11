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
        Tests the ability to add a custom filter to the library.

        Verifies that the filter is successfully registered and stored
        in the library's filters dictionary, making it available for use.

        The test adds a simple filter function that returns an empty string,
        and then asserts that the filter is correctly stored in the library.
        This ensures that the filter registration mechanism is working as expected.
        """
        def func():
            return ""

        self.assertEqual(self.library.filters["func"], func)

    def test_filter_parens(self):
        @self.library.filter()
        """

        Tests the filtering functionality by applying a decorator to a function and verifying its existence in the library's filters dictionary.

        The test creates a simple function, adds it as a filter to the library, and checks if the function is correctly registered under its expected name.

        """
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
        Tests that a filter is correctly registered with the specified name using the 'name' keyword argument.

        This test verifies that when a filter is decorated with the library's filter decorator and a name is provided,
        the filter is properly stored in the library's filters dictionary under the given name.
        """
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
        Test that filtering with invalid arguments raises a ValueError.

        This test case verifies that the Library.filter method correctly handles invalid input arguments.
        It checks that passing None and an empty string as arguments raises a ValueError with a specific error message.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError: If invalid arguments are passed to the Library.filter method
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
        """
        Tests that an inclusion tag name is correctly registered in the library.

        Checks that when an inclusion tag is created with a specified name, it can be
        found in the library's tags dictionary, allowing for proper lookup and usage.

        This ensures that the name provided to the inclusion tag decorator is properly
        retained and can be used to identify the tag in the library's collection of tags.
        """
        def func():
            return ""

        self.assertIn("name", self.library.tags)

    def test_inclusion_tag_wrapped(self):
        @self.library.inclusion_tag("template.html")
        @functools.lru_cache(maxsize=32)
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
        Tests the registration of a simple tag.

        Verifies that a newly defined simple tag function is correctly added to the library's tags dictionary, ensuring it can be accessed and utilized as expected.

        The test defines a minimal tag function and then checks for its presence in the library's tags collection, confirming successful registration.
        """
        def func():
            return ""

        self.assertIn("func", self.library.tags)

    def test_simple_tag_parens(self):
        @self.library.simple_tag()
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
        """
        Tests that a simple tag wrapped by the library retains its original function while also including caching functionality. 

        The wrapped function is verified to be the same as the original, and it is checked for the presence of a cache information attribute, indicating that the caching decorator has been successfully applied.
        """
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

        Tests that a function decorated with the @library.tag decorator is correctly registered 
        in the library's tags dictionary.

        The test verifies that the decorated function is assigned to the corresponding tag 
        name in the library, ensuring that the tagging mechanism is functioning as expected.

        """
        def func(parser, token):
            return Node()

        self.assertEqual(self.library.tags["name"], func)

    def test_tag_name_kwarg(self):
        @self.library.tag(name="name")
        """
        Tests that the tag_name keyword argument is correctly used to identify a custom tag function.

        This test ensures that when a tag is defined with a specific name using the @library.tag decorator,
        the corresponding function is correctly associated with the tag name in the library's tags dictionary.

        The test validates that the function associated with the 'name' tag in the library is indeed the function that was decorated with @library.tag(name='name').
        """
        def func(parser, token):
            return Node()

        self.assertEqual(self.library.tags["name"], func)

    def test_tag_call(self):
        """
        Tests the registration of a custom tag with the library.

        Verifies that a tag can be successfully added to the library using the
        :obj:`.tag` method, and that the assigned function is correctly stored.

        This ensures that custom tags can be seamlessly integrated into the library,
        enabling developers to extend its functionality as needed.
        """
        def func(parser, token):
            return Node()

        self.library.tag("name", func)
        self.assertEqual(self.library.tags["name"], func)

    def test_tag_invalid(self):
        """

        Tests the behavior of the Library.tag method when passed invalid arguments.

        Specifically, this test checks that a ValueError is raised when the method is called with a tag of None and an empty string.

        The expected error message is \"Unsupported arguments to Library.tag: (None, '')\", which is validated to ensure correct error handling.

        """
        msg = "Unsupported arguments to Library.tag: (None, '')"
        with self.assertRaisesMessage(ValueError, msg):
            self.library.tag(None, "")
