from django.template.defaultfilters import make_list
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class MakeListTests(SimpleTestCase):
    """
    The make_list filter can destroy existing escaping, so the results are
    escaped.
    """

    @setup({"make_list01": "{% autoescape off %}{{ a|make_list }}{% endautoescape %}"})
    def test_make_list01(self):
        output = self.engine.render_to_string("make_list01", {"a": mark_safe("&")})
        self.assertEqual(output, "['&']")

    @setup({"make_list02": "{{ a|make_list }}"})
    def test_make_list02(self):
        """

        Test the make_list filter with a string containing special characters.

        This test ensures that the make_list filter correctly handles a string containing
        an ampersand (&) character, and that the output is properly escaped and formatted
        as a list.

        The expected output is a list containing a single string element, where the
        ampersand character is properly escaped as '&#x27;&amp;&#x27;'.

        """
        output = self.engine.render_to_string("make_list02", {"a": mark_safe("&")})
        self.assertEqual(output, "[&#x27;&amp;&#x27;]")

    @setup(
        {
            "make_list03": (
                '{% autoescape off %}{{ a|make_list|stringformat:"s"|safe }}'
                "{% endautoescape %}"
            )
        }
    )
    def test_make_list03(self):
        output = self.engine.render_to_string("make_list03", {"a": mark_safe("&")})
        self.assertEqual(output, "['&']")

    @setup({"make_list04": '{{ a|make_list|stringformat:"s"|safe }}'})
    def test_make_list04(self):
        """

        Tests the make_list filter in a templating engine.

        This function checks if the make_list filter correctly converts a string into a list
        when the string contains special characters. It verifies that the output is a string
        representation of a list containing the input string as its only element.

        The test case specifically targets the handling of ampersand (&) characters, ensuring
        that they are properly escaped and included in the output list.

        """
        output = self.engine.render_to_string("make_list04", {"a": mark_safe("&")})
        self.assertEqual(output, "['&']")


class FunctionTests(SimpleTestCase):
    def test_string(self):
        self.assertEqual(make_list("abc"), ["a", "b", "c"])

    def test_integer(self):
        self.assertEqual(make_list(1234), ["1", "2", "3", "4"])
