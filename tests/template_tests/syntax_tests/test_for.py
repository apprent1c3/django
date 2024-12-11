from django.template import TemplateSyntaxError
from django.template.defaulttags import ForNode
from django.test import SimpleTestCase

from ..utils import setup


class ForTagTests(SimpleTestCase):
    libraries = {"custom": "template_tests.templatetags.custom"}

    @setup({"for-tag01": "{% for val in values %}{{ val }}{% endfor %}"})
    def test_for_tag01(self):
        """
        Tests the functionality of a for loop tag in a templating engine, 
        verifying that it correctly iterates over a list of values and renders them 
        as a concatenated string. The test input is a list of integers and the 
        expected output is a string containing the concatenated values.
        """
        output = self.engine.render_to_string("for-tag01", {"values": [1, 2, 3]})
        self.assertEqual(output, "123")

    @setup({"for-tag02": "{% for val in values reversed %}{{ val }}{% endfor %}"})
    def test_for_tag02(self):
        output = self.engine.render_to_string("for-tag02", {"values": [1, 2, 3]})
        self.assertEqual(output, "321")

    @setup(
        {"for-tag-vars01": "{% for val in values %}{{ forloop.counter }}{% endfor %}"}
    )
    def test_for_tag_vars01(self):
        """

        Tests the rendering of the 'for' template tag with loop counter variables.

        This test case verifies that the 'forloop.counter' variable correctly
        increments and displays the loop index during the iteration of a list.
        It checks if the rendered output matches the expected string.

        The test uses a predefined template string containing a 'for' loop, 
        which iterates over a list of values and outputs the 'forloop.counter' 
        variable on each iteration. The test passes if the rendered output
        matches the expected string '123', indicating that the loop counter 
        variable was correctly displayed during the iteration.

        """
        output = self.engine.render_to_string("for-tag-vars01", {"values": [6, 6, 6]})
        self.assertEqual(output, "123")

    @setup(
        {"for-tag-vars02": "{% for val in values %}{{ forloop.counter0 }}{% endfor %}"}
    )
    def test_for_tag_vars02(self):
        output = self.engine.render_to_string("for-tag-vars02", {"values": [6, 6, 6]})
        self.assertEqual(output, "012")

    @setup(
        {
            "for-tag-vars03": (
                "{% for val in values %}{{ forloop.revcounter }}{% endfor %}"
            )
        }
    )
    def test_for_tag_vars03(self):
        """
        Tests the 'forloop.revcounter' variable in a for loop, verifying it correctly returns the reverse counter value.

         The test checks the rendering of a template that iterates over a list of values and outputs the reverse counter for each iteration.

         :return: None
        """
        output = self.engine.render_to_string("for-tag-vars03", {"values": [6, 6, 6]})
        self.assertEqual(output, "321")

    @setup(
        {
            "for-tag-vars04": (
                "{% for val in values %}{{ forloop.revcounter0 }}{% endfor %}"
            )
        }
    )
    def test_for_tag_vars04(self):
        """

        Tests the forloop.revcounter0 variable in a for loop within a template.

        The forloop.revcounter0 variable returns the current iteration of the loop
        (1-indexed and reversed). This test ensures that the templating engine correctly
        renders the forloop.revcounter0 variable when iterating over a list of values.

        :param none:
        :returns: none
        :raises: AssertionError if the output does not match the expected value.

        """
        output = self.engine.render_to_string("for-tag-vars04", {"values": [6, 6, 6]})
        self.assertEqual(output, "210")

    @setup(
        {
            "for-tag-vars05": "{% for val in values %}"
            "{% if forloop.first %}f{% else %}x{% endif %}{% endfor %}"
        }
    )
    def test_for_tag_vars05(self):
        output = self.engine.render_to_string("for-tag-vars05", {"values": [6, 6, 6]})
        self.assertEqual(output, "fxx")

    @setup(
        {
            "for-tag-vars06": "{% for val in values %}"
            "{% if forloop.last %}l{% else %}x{% endif %}{% endfor %}"
        }
    )
    def test_for_tag_vars06(self):
        """
        #: Tests the rendering of a template with a for loop that uses variables.
        #: 
        #: This test case verifies that the template engine correctly interprets and renders
        #: a for loop that utilizes variables, specifically the `forloop.last` variable, which
        #: is used to apply a different value to the last item in the loop.
        #: 
        #: The expected output is a string where all but the last item in the loop are replaced
        #: with a specific character ('x'), and the last item is replaced with another character ('l').
        """
        output = self.engine.render_to_string("for-tag-vars06", {"values": [6, 6, 6]})
        self.assertEqual(output, "xxl")

    @setup(
        {
            "for-tag-unpack01": (
                "{% for key,value in items %}{{ key }}:{{ value }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack01(self):
        """
        Test the for tag unpack functionality in templating engine.

        This test case verifies that the engine can correctly unpack key-value pairs 
        from a sequence of tuples and render them according to the provided template.

        The test template includes a for loop that iterates over the 'items' sequence, 
        unpacking each tuple into 'key' and 'value' variables, and renders them as 'key:value/'.

        The expected output is a string where each key-value pair is rendered in the 
        above format, separated by a forward slash, with a trailing forward slash.\"\"\")
        """
        output = self.engine.render_to_string(
            "for-tag-unpack01", {"items": (("one", 1), ("two", 2))}
        )
        self.assertEqual(output, "one:1/two:2/")

    @setup(
        {
            "for-tag-unpack03": (
                "{% for key, value in items %}{{ key }}:{{ value }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack03(self):
        output = self.engine.render_to_string(
            "for-tag-unpack03", {"items": (("one", 1), ("two", 2))}
        )
        self.assertEqual(output, "one:1/two:2/")

    @setup(
        {
            "for-tag-unpack04": (
                "{% for key , value in items %}{{ key }}:{{ value }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack04(self):
        """
        '/../
        Tests the for-tag unpack functionality with key-value pairs.

        Checks that the output of the template rendering matches the expected string.
        The test case provides a dictionary with key-value pairs and verifies that the
        for-tag correctly unpacks these pairs and renders them as a string in the
        format 'key:value/'. 

        :raises AssertionError: if the output of the template rendering does not match 
            the expected string.
        '/../
        """
        output = self.engine.render_to_string(
            "for-tag-unpack04", {"items": (("one", 1), ("two", 2))}
        )
        self.assertEqual(output, "one:1/two:2/")

    @setup(
        {
            "for-tag-unpack05": (
                "{% for key ,value in items %}{{ key }}:{{ value }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack05(self):
        """

        Tests the unpacking of key-value pairs in a for loop within a template.

        This test case verifies that the for loop can correctly unpack key-value pairs
        from an iterable of tuples and render the expected output.

        The input data is a collection of tuples, where each tuple contains a key-value
        pair. The test checks that the template engine can iterate over this data,
        unpack the key-value pairs, and render them in the desired format.

        The expected output is a string containing the key-value pairs, separated by
        forward slashes, with each key-value pair in the format \"key:value\".

        """
        output = self.engine.render_to_string(
            "for-tag-unpack05", {"items": (("one", 1), ("two", 2))}
        )
        self.assertEqual(output, "one:1/two:2/")

    @setup(
        {
            "for-tag-unpack06": (
                "{% for key value in items %}{{ key }}:{{ value }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack06(self):
        msg = "'for' tag received an invalid argument: for key value in items"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string(
                "for-tag-unpack06", {"items": (("one", 1), ("two", 2))}
            )

    @setup(
        {
            "for-tag-unpack07": (
                "{% for key,,value in items %}{{ key }}:{{ value }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack07(self):
        msg = "'for' tag received an invalid argument: for key,,value in items"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string(
                "for-tag-unpack07", {"items": (("one", 1), ("two", 2))}
            )

    @setup(
        {
            "for-tag-unpack08": (
                "{% for key,value, in items %}{{ key }}:{{ value }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack08(self):
        msg = "'for' tag received an invalid argument: for key,value, in items"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string(
                "for-tag-unpack08", {"items": (("one", 1), ("two", 2))}
            )

    @setup({"double-quote": '{% for "k" in items %}{{ "k" }}/{% endfor %}'})
    def test_unpack_double_quote(self):
        msg = """'for' tag received an invalid argument: for "k" in items"""
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("double-quote", {"items": (1, 2)})

    @setup({"single-quote": "{% for 'k' in items %}{{ k }}/{% endfor %}"})
    def test_unpack_single_quote(self):
        """
        Tests that a TemplateSyntaxError is raised when single quotes are used in a 'for' loop within a template.

        This test case checks that the templating engine correctly identifies and fails on invalid syntax where single quotes are used in place of the expected double quotes in a 'for' loop declaration. It verifies that the error message matches the expected output, confirming the engine's ability to handle and report this specific type of syntax error.

        :raises: TemplateSyntaxError with the specified error message when rendering the template with single quotes in the 'for' loop
        """
        msg = """'for' tag received an invalid argument: for 'k' in items"""
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("single-quote", {"items": (1, 2)})

    @setup({"vertical-bar": "{% for k|upper in items %}{{ k|upper }}/{% endfor %}"})
    def test_unpack_vertical_bar(self):
        """

        Test that the unpacking of a vertical bar within a 'for' loop in a template results in a TemplateSyntaxError.

        This test case ensures that the template engine correctly raises an error when attempting to unpack a vertical bar in a 'for' loop. The test verifies that the expected error message is raised when the engine is rendering a template with a 'for' loop that contains a vertical bar.

        """
        msg = "'for' tag received an invalid argument: for k|upper in items"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("vertical-bar", {"items": (1, 2)})

    @setup(
        {
            "for-tag-unpack09": (
                "{% for val in items %}{{ val.0 }}:{{ val.1 }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack09(self):
        """
        A single loopvar doesn't truncate the list in val.
        """
        output = self.engine.render_to_string(
            "for-tag-unpack09", {"items": (("one", 1), ("two", 2))}
        )
        self.assertEqual(output, "one:1/two:2/")

    @setup(
        {
            "for-tag-unpack13": (
                "{% for x,y,z in items %}{{ x }}:{{ y }},{{ z }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack13(self):
        output = self.engine.render_to_string(
            "for-tag-unpack13", {"items": (("one", 1, "carrot"), ("two", 2, "cheese"))}
        )
        if self.engine.string_if_invalid:
            self.assertEqual(output, "one:1,carrot/two:2,cheese/")
        else:
            self.assertEqual(output, "one:1,carrot/two:2,cheese/")

    @setup(
        {
            "for-tag-empty01": (
                "{% for val in values %}{{ val }}{% empty %}empty text{% endfor %}"
            )
        }
    )
    def test_for_tag_empty01(self):
        """

        Tests the for tag with an empty fallback in a template engine.

        This test case verifies that when a for loop is rendered with a non-empty list of values,
        the loop iterates over the values and renders them correctly.
        The empty fallback is not rendered in this scenario.

        The expected output is a concatenated string of the values in the list.

        """
        output = self.engine.render_to_string("for-tag-empty01", {"values": [1, 2, 3]})
        self.assertEqual(output, "123")

    @setup(
        {
            "for-tag-empty02": (
                "{% for val in values %}{{ val }}{% empty %}values array empty"
                "{% endfor %}"
            )
        }
    )
    def test_for_tag_empty02(self):
        """
        Tests the rendering of a for tag with an empty list, verifying that the empty block is correctly displayed when the list is empty.

        The test case checks if the templating engine properly handles a for loop with no items in the iterable, ensuring that the empty message is rendered as expected. This helps to guarantee that the engine behaves correctly when dealing with empty collections in for loops, providing the desired output in such scenarios.
        """
        output = self.engine.render_to_string("for-tag-empty02", {"values": []})
        self.assertEqual(output, "values array empty")

    @setup(
        {
            "for-tag-empty03": "{% for val in values %}"
            "{{ val }}{% empty %}values array not found{% endfor %}"
        }
    )
    def test_for_tag_empty03(self):
        output = self.engine.render_to_string("for-tag-empty03")
        self.assertEqual(output, "values array not found")

    @setup(
        {
            "for-tag-filter-ws": (
                "{% load custom %}{% for x in s|noop:'x y' %}{{ x }}{% endfor %}"
            )
        }
    )
    def test_for_tag_filter_ws(self):
        """
        #19882
        """
        output = self.engine.render_to_string("for-tag-filter-ws", {"s": "abc"})
        self.assertEqual(output, "abc")

    @setup(
        {"for-tag-unpack-strs": "{% for x,y in items %}{{ x }}:{{ y }}/{% endfor %}"}
    )
    def test_for_tag_unpack_strs(self):
        """

        Tests the for tag unpacking in the templating engine with string tuples.

        Verifies that the for loop can unpack string tuples into separate variables, 
        and that the templating engine correctly renders the template with the unpacked values.

        """
        output = self.engine.render_to_string(
            "for-tag-unpack-strs", {"items": ("ab", "ac")}
        )
        self.assertEqual(output, "a:b/a:c/")

    @setup({"for-tag-unpack10": "{% for x,y in items %}{{ x }}:{{ y }}/{% endfor %}"})
    def test_for_tag_unpack10(self):
        """
        Tests that the for loop in the templating engine correctly raises an error when attempting to unpack a tuple with more than two values.

        The test case verifies that a ValueError is raised with the expected error message when the engine is asked to render a template that includes a for loop trying to unpack three values into two variables.

        """
        with self.assertRaisesMessage(
            ValueError, "Need 2 values to unpack in for loop; got 3."
        ):
            self.engine.render_to_string(
                "for-tag-unpack10",
                {"items": (("one", 1, "carrot"), ("two", 2, "orange"))},
            )

    @setup(
        {
            "for-tag-unpack11": (
                "{% for x,y,z in items %}{{ x }}:{{ y }},{{ z }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack11(self):
        with self.assertRaisesMessage(
            ValueError, "Need 3 values to unpack in for loop; got 2."
        ):
            self.engine.render_to_string(
                "for-tag-unpack11",
                {"items": (("one", 1), ("two", 2))},
            )

    @setup(
        {
            "for-tag-unpack12": (
                "{% for x,y,z in items %}{{ x }}:{{ y }},{{ z }}/{% endfor %}"
            )
        }
    )
    def test_for_tag_unpack12(self):
        """

        Tests that a ValueError is raised when the number of values to unpack in a for loop
        does not match the number of values provided in each item.

        This test case ensures that the templating engine enforces the correct unpacking of values
        in a for loop, and provides a meaningful error message when the unpacking fails.

        """
        with self.assertRaisesMessage(
            ValueError, "Need 3 values to unpack in for loop; got 2."
        ):
            self.engine.render_to_string(
                "for-tag-unpack12", {"items": (("one", 1, "carrot"), ("two", 2))}
            )

    @setup({"for-tag-unpack14": "{% for x,y in items %}{{ x }}:{{ y }}/{% endfor %}"})
    def test_for_tag_unpack14(self):
        """

        Test that a ValueError is raised when using the 'for' tag with unpacking and the item has an incorrect number of values.

        The purpose of this test is to ensure that the templating engine correctly handles iteration over items with the wrong number of values to unpack. It verifies that a ValueError is raised with a meaningful error message when the number of values in the item does not match the number of variables in the 'for' tag.

        This test case specifically checks that the error message 'Need 2 values to unpack in for loop; got 1.' is raised when the item has only one value.

        """
        with self.assertRaisesMessage(
            ValueError, "Need 2 values to unpack in for loop; got 1."
        ):
            self.engine.render_to_string("for-tag-unpack14", {"items": (1, 2)})

    @setup(
        {
            "main": '{% with alpha=alpha.values %}{% include "base" %}{% endwith %}_'
            '{% with alpha=alpha.extra %}{% include "base" %}{% endwith %}',
            "base": "{% for x, y in alpha %}{{ x }}:{{ y }},{% endfor %}",
        }
    )
    def test_for_tag_context(self):
        """
        ForNode.render() pops the values it pushes to the context (#28001).
        """
        output = self.engine.render_to_string(
            "main",
            {
                "alpha": {
                    "values": [("two", 2), ("four", 4)],
                    "extra": [("six", 6), ("eight", 8)],
                },
            },
        )
        self.assertEqual(output, "two:2,four:4,_six:6,eight:8,")

    @setup({"invalid_for_loop": "{% for x items %}{{ x }}{% endfor %}"})
    def test_invalid_arg(self):
        """

        Tests the rendering of a template with an invalid 'for' loop argument.

        This function verifies that a TemplateSyntaxError is raised when the 'for' loop
        syntax is incorrect, specifically when there are not enough words to specify
        the loop variable and the iterable. The test checks that the error message
        provided is as expected.

        The test case uses a deliberately invalid template and verifies that the
        exception message matches the expected error message.

        """
        msg = "'for' statements should have at least four words: for x items"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("invalid_for_loop", {"items": (1, 2)})

    @setup({"invalid_for_loop": "{% for x from items %}{{ x }}{% endfor %}"})
    def test_invalid_in_keyword(self):
        """
        Tests that using an invalid 'for' loop syntax in a template raises a TemplateSyntaxError.

        The test verifies that the template engine correctly identifies and reports syntax errors
        when the 'for' loop is not used with the 'in' keyword, as required by the template syntax.

        Args:
            None

        Returns:
            None

        Raises:
            TemplateSyntaxError: if the template engine encounters an invalid 'for' loop syntax.

        Note:
            This test ensures that the template engine enforces the correct syntax for 'for' loops,
            which is essential for preventing template rendering errors and providing informative error messages.

        """
        msg = "'for' statements should use the format 'for x in y': for x from items"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("invalid_for_loop", {"items": (1, 2)})


class ForNodeTests(SimpleTestCase):
    def test_repr(self):
        node = ForNode(
            "x",
            "sequence",
            is_reversed=True,
            nodelist_loop=["val"],
            nodelist_empty=["val2"],
        )
        self.assertEqual(
            repr(node), "<ForNode: for x in sequence, tail_len: 1 reversed>"
        )
