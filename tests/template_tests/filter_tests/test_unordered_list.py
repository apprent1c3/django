from django.template.defaultfilters import unordered_list
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy

from ..utils import setup


class UnorderedListTests(SimpleTestCase):
    @setup({"unordered_list01": "{{ a|unordered_list }}"})
    def test_unordered_list01(self):
        """
        Tests rendering of an unordered list with a nested list.

        This test case verifies that the unordered list template is correctly rendered
        when the input data contains a list with a nested list as an item. The expected
        output is an HTML unordered list with a nested unordered list.

        Args:
            None (test case input data is predefined)

        Returns:
            None (the test case asserts the rendered output matches the expected result)

        Note:
            This test case covers a specific edge case where the input list contains HTML
            special characters and a nested list, ensuring the renderer correctly escapes
            and formats the output.
        """
        output = self.engine.render_to_string("unordered_list01", {"a": ["x>", ["<y"]]})
        self.assertEqual(
            output, "\t<li>x&gt;\n\t<ul>\n\t\t<li>&lt;y</li>\n\t</ul>\n\t</li>"
        )

    @setup(
        {
            "unordered_list02": (
                "{% autoescape off %}{{ a|unordered_list }}{% endautoescape %}"
            )
        }
    )
    def test_unordered_list02(self):
        output = self.engine.render_to_string("unordered_list02", {"a": ["x>", ["<y"]]})
        self.assertEqual(output, "\t<li>x>\n\t<ul>\n\t\t<li><y</li>\n\t</ul>\n\t</li>")

    @setup({"unordered_list03": "{{ a|unordered_list }}"})
    def test_unordered_list03(self):
        """
        Tests the rendering of nested unordered lists within an unordered list item.

        The function verifies that the template engine correctly handles HTML-escaped characters 
        and marked-safe content when generating nested unordered lists. It checks the output 
        against an expected string, ensuring that the list items are properly formatted and 
        that HTML tags are correctly escaped or rendered, depending on their safety status.
        """
        output = self.engine.render_to_string(
            "unordered_list03", {"a": ["x>", [mark_safe("<y")]]}
        )
        self.assertEqual(
            output, "\t<li>x&gt;\n\t<ul>\n\t\t<li><y</li>\n\t</ul>\n\t</li>"
        )

    @setup(
        {
            "unordered_list04": (
                "{% autoescape off %}{{ a|unordered_list }}{% endautoescape %}"
            )
        }
    )
    def test_unordered_list04(self):
        """

        Tests the rendering of an unordered list with nested list items.

        The test case verifies that the template engine correctly interprets the input data and
        produces the expected HTML output, including the proper indentation and tags for the list items.
        The input data includes a list with a string and a nested list containing a markup-safe string,
        ensuring that the template engine handles the nested structure and HTML escaping correctly.

        """
        output = self.engine.render_to_string(
            "unordered_list04", {"a": ["x>", [mark_safe("<y")]]}
        )
        self.assertEqual(output, "\t<li>x>\n\t<ul>\n\t\t<li><y</li>\n\t</ul>\n\t</li>")

    @setup(
        {
            "unordered_list05": (
                "{% autoescape off %}{{ a|unordered_list }}{% endautoescape %}"
            )
        }
    )
    def test_unordered_list05(self):
        output = self.engine.render_to_string("unordered_list05", {"a": ["x>", ["<y"]]})
        self.assertEqual(output, "\t<li>x>\n\t<ul>\n\t\t<li><y</li>\n\t</ul>\n\t</li>")


class FunctionTests(SimpleTestCase):
    def test_list(self):
        self.assertEqual(
            unordered_list(["item 1", "item 2"]), "\t<li>item 1</li>\n\t<li>item 2</li>"
        )

    def test_list_gettext(self):
        self.assertEqual(
            unordered_list(["item 1", gettext_lazy("item 2")]),
            "\t<li>item 1</li>\n\t<li>item 2</li>",
        )

    def test_nested(self):
        self.assertEqual(
            unordered_list(["item 1", ["item 1.1"]]),
            "\t<li>item 1\n\t<ul>\n\t\t<li>item 1.1</li>\n\t</ul>\n\t</li>",
        )

    def test_nested2(self):
        self.assertEqual(
            unordered_list(["item 1", ["item 1.1", "item1.2"], "item 2"]),
            "\t<li>item 1\n\t<ul>\n\t\t<li>item 1.1</li>\n\t\t<li>item1.2"
            "</li>\n\t</ul>\n\t</li>\n\t<li>item 2</li>",
        )

    def test_nested3(self):
        self.assertEqual(
            unordered_list(["item 1", "item 2", ["item 2.1"]]),
            "\t<li>item 1</li>\n\t<li>item 2\n\t<ul>\n\t\t<li>item 2.1"
            "</li>\n\t</ul>\n\t</li>",
        )

    def test_nested_multiple(self):
        self.assertEqual(
            unordered_list(["item 1", ["item 1.1", ["item 1.1.1", ["item 1.1.1.1"]]]]),
            "\t<li>item 1\n\t<ul>\n\t\t<li>item 1.1\n\t\t<ul>\n\t\t\t<li>"
            "item 1.1.1\n\t\t\t<ul>\n\t\t\t\t<li>item 1.1.1.1</li>\n\t\t\t"
            "</ul>\n\t\t\t</li>\n\t\t</ul>\n\t\t</li>\n\t</ul>\n\t</li>",
        )

    def test_nested_multiple2(self):
        self.assertEqual(
            unordered_list(["States", ["Kansas", ["Lawrence", "Topeka"], "Illinois"]]),
            "\t<li>States\n\t<ul>\n\t\t<li>Kansas\n\t\t<ul>\n\t\t\t<li>"
            "Lawrence</li>\n\t\t\t<li>Topeka</li>\n\t\t</ul>\n\t\t</li>"
            "\n\t\t<li>Illinois</li>\n\t</ul>\n\t</li>",
        )

    def test_autoescape(self):
        self.assertEqual(
            unordered_list(["<a>item 1</a>", "item 2"]),
            "\t<li>&lt;a&gt;item 1&lt;/a&gt;</li>\n\t<li>item 2</li>",
        )

    def test_autoescape_off(self):
        self.assertEqual(
            unordered_list(["<a>item 1</a>", "item 2"], autoescape=False),
            "\t<li><a>item 1</a></li>\n\t<li>item 2</li>",
        )

    def test_ulitem(self):
        """

        Tests the generation of an unordered list given a collection of ULItem objects.

        The test covers two scenarios: passing in a list of ULItem objects and passing in a generator that yields ULItem objects.

        In both cases, the expected output is an unordered list where each item is represented as a list item element (<li>) containing the string representation of the corresponding ULItem object.

        The test also checks for proper HTML escaping of special characters in the item titles.

        """
        class ULItem:
            def __init__(self, title):
                self.title = title

            def __str__(self):
                return "ulitem-%s" % str(self.title)

        a = ULItem("a")
        b = ULItem("b")
        c = ULItem("<a>c</a>")
        self.assertEqual(
            unordered_list([a, b, c]),
            "\t<li>ulitem-a</li>\n\t<li>ulitem-b</li>\n\t"
            "<li>ulitem-&lt;a&gt;c&lt;/a&gt;</li>",
        )

        def item_generator():
            yield from (a, b, c)

        self.assertEqual(
            unordered_list(item_generator()),
            "\t<li>ulitem-a</li>\n\t<li>ulitem-b</li>\n\t"
            "<li>ulitem-&lt;a&gt;c&lt;/a&gt;</li>",
        )

    def test_nested_generators(self):
        """

        Tests the generation of unordered HTML lists from nested generators.

        This test case verifies that the unordered_list function correctly handles nested generators, 
        where an inner generator yields items that should be wrapped in a nested unordered list. 
        The expected output is a single top-level list item containing an unordered list with two items, 
        followed by a second top-level list item. 

        """
        def inner_generator():
            yield from ("B", "C")

        def item_generator():
            """
            Generates a sequence of items.

            This function produces a series of values, including strings and the output of inner_generator, which is another iterable.

            The sequence yielded by this function consists of three items: 'A', the values produced by inner_generator, and 'D'.

            Yielded values are produced on-the-fly, allowing for efficient handling of large datasets.

            Returns:
                An iterator yielding the generated items in sequence.
            """
            yield "A"
            yield inner_generator()
            yield "D"

        self.assertEqual(
            unordered_list(item_generator()),
            "\t<li>A\n\t<ul>\n\t\t<li>B</li>\n\t\t<li>C</li>\n\t</ul>\n\t</li>\n\t"
            "<li>D</li>",
        )

    def test_ulitem_autoescape_off(self):
        """

        Tests the behavior of the unordered_list function when autoescaping is disabled.

        This test case verifies that the unordered_list function correctly handles a list of items 
        without escaping any HTML characters in the item titles. It also ensures that the function 
        works with both lists and generators of items, producing the same output in both cases.

        The function's output is checked to ensure that it correctly generates an unordered list 
        with the expected items, without modifying any HTML characters in the item titles.

        """
        class ULItem:
            def __init__(self, title):
                self.title = title

            def __str__(self):
                return "ulitem-%s" % str(self.title)

        a = ULItem("a")
        b = ULItem("b")
        c = ULItem("<a>c</a>")
        self.assertEqual(
            unordered_list([a, b, c], autoescape=False),
            "\t<li>ulitem-a</li>\n\t<li>ulitem-b</li>\n\t<li>ulitem-<a>c</a></li>",
        )

        def item_generator():
            yield from (a, b, c)

        self.assertEqual(
            unordered_list(item_generator(), autoescape=False),
            "\t<li>ulitem-a</li>\n\t<li>ulitem-b</li>\n\t<li>ulitem-<a>c</a></li>",
        )
