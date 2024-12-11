from django.template import TemplateSyntaxError
from django.template.defaulttags import ForNode
from django.test import SimpleTestCase

from ..utils import setup


class ForTagTests(SimpleTestCase):
    libraries = {"custom": "template_tests.templatetags.custom"}

    @setup({"for-tag01": "{% for val in values %}{{ val }}{% endfor %}"})
    def test_for_tag01(self):
        """

        Tests the rendering of a for loop template tag.

        This test case checks that the templating engine correctly renders a for loop,
        iterating over a list of values and outputting them as a concatenated string.

        :raises AssertionError: If the rendered output does not match the expected result.

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
        Tests the forloop.counter variable in a for loop, ensuring that it correctly increments and outputs the expected sequence of numbers.

        The test provides a list of values and checks that the rendered output matches the expected result, confirming that the forloop.counter variable behaves as expected when used within a for loop in a template.

        :param self: The test instance
        :return: None
        :raises AssertionError: If the rendered output does not match the expected result
        """
        output = self.engine.render_to_string("for-tag-vars01", {"values": [6, 6, 6]})
        self.assertEqual(output, "123")

    @setup(
        {"for-tag-vars02": "{% for val in values %}{{ forloop.counter0 }}{% endfor %}"}
    )
    def test_for_tag_vars02(self):
        """

        Tests the forloop.counter0 variable in a for loop template tag.

        This test case verifies that the forloop.counter0 variable is correctly 
        incremented and rendered within a for loop in a template, starting from 
        0 and incrementing up to the last iteration.

        The test passes when the rendered template output matches the expected string.

        """
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

        Tests the functionality of the forloop.revcounter variable in a for loop.

        This test case verifies that the forloop.revcounter variable correctly counts down 
        from the total number of items in the loop, even when all items in the list are identical.

        The expected output is a string containing the reversed counter values, separated by 
        no spaces.

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
        output = self.engine.render_to_string("for-tag-vars04", {"values": [6, 6, 6]})
        self.assertEqual(output, "210")

    @setup(
        {
            "for-tag-vars05": "{% for val in values %}"
            "{% if forloop.first %}f{% else %}x{% endif %}{% endfor %}"
        }
    )
    def test_for_tag_vars05(self):
        """
        Tests the behavior of for loop variables in a templating engine, specifically verifying that the 'forloop.first' variable is correctly set to True for the first iteration and False otherwise, and that this variable affects the output of the template as expected.
        """
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

        Tests the functionality of the forloop variable in a Jinja2 for loop.

        This test verifies that the forloop variable correctly identifies the last item in a loop.
        The test case uses a template that renders 'x' for all but the last item, and 'l' for the last item.
        The result is then compared to the expected output to ensure the forloop variable is working as intended.

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

        Tests the unpacking of key-value pairs in a for loop using the {%% for key, value in items %%} syntax.

        The test case renders a template with a for loop that unpacks key-value pairs from an iterable of tuples. It then verifies that the rendered output matches the expected string, which includes the unpacked key-value pairs separated by a colon and a slash.

        :param self: The test instance
        :return: None

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
        """

        Tests the unpacking of values in the 'for' tag with an invalid argument.

        Verifies that a TemplateSyntaxError is raised when the 'for' tag is given an argument
        in the form 'for key value in items' instead of the correct syntax 'for key, value in items'.

        Ensures the error message is correctly displayed, indicating the invalid argument passed
        to the 'for' tag.

        """
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
        msg = """'for' tag received an invalid argument: for 'k' in items"""
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("single-quote", {"items": (1, 2)})

    @setup({"vertical-bar": "{% for k|upper in items %}{{ k|upper }}/{% endfor %}"})
    def test_unpack_vertical_bar(self):
        """
        Tests that the template engine correctly raises an error when using theDALR 'for' tag with a tuple that is unpacked in an invalid way.

        The test case exercises a 'for' loop in a template where the loop variable has a filter applied to it and the loop iterates over a tuple of items. It verifies that a TemplateSyntaxError is raised when the argument passed to the 'for' tag is invalid, specifically when a tuple is passed where a sequence is expected and an item in that sequence has a filter applied to it.
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
        Tests the for tag with an empty list, ensuring the empty clause is executed.

        The function verifies that when the for loop has no values to iterate over, 
        the empty clause within the for tag is correctly rendered, 
        displaying a message indicating that the values array is empty.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the rendered output does not match the expected string.

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
        Tests the unpacking of string items in a for loop within a templating engine.

        This test ensures that when strings are unpacked into two variables within a for loop,
        the rendering engine correctly handles the unpacking and produces the expected output.

        The test uses a predefined template 'for-tag-unpack-strs' and passes a tuple of strings
        as input to the rendering engine. It then verifies that the rendered output matches
        the expected format, where each item in the tuple is unpacked and displayed in the
        format 'x:y/'.

        The successful execution of this test confirms that the templating engine correctly
        supports the unpacking of string items in for loops, allowing for more flexible and
        dynamic template rendering.
        """
        output = self.engine.render_to_string(
            "for-tag-unpack-strs", {"items": ("ab", "ac")}
        )
        self.assertEqual(output, "a:b/a:c/")

    @setup({"for-tag-unpack10": "{% for x,y in items %}{{ x }}:{{ y }}/{% endfor %}"})
    def test_for_tag_unpack10(self):
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
        with self.assertRaisesMessage(
            ValueError, "Need 3 values to unpack in for loop; got 2."
        ):
            self.engine.render_to_string(
                "for-tag-unpack12", {"items": (("one", 1, "carrot"), ("two", 2))}
            )

    @setup({"for-tag-unpack14": "{% for x,y in items %}{{ x }}:{{ y }}/{% endfor %}"})
    def test_for_tag_unpack14(self):
        """
        Tests that the template engine correctly raises a ValueError when using the 'for' tag with unpacking and the iterable contains a tuple with an incorrect number of values.

        The test case verifies that providing a tuple with only one value results in a ValueError, as the 'for' tag expects two values to unpack in this scenario.

        Raises:
            ValueError: With a message indicating that 2 values are needed to unpack in the for loop, but only 1 was provided.
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
        Tests the handling of invalid for loops in templating.

        Verifies that a TemplateSyntaxError is raised when a for loop is used with
        an invalid syntax, specifically when the loop statement does not contain
        at least four words (e.g. \"for x in items\"). The test checks that the
        correct error message is displayed when rendering a template with an
        invalid for loop.

        The test uses a template string containing an intentionally incorrect
        for loop syntax, and asserts that the expected error message is raised
        when attempting to render the template with a given context.

        """
        msg = "'for' statements should have at least four words: for x items"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("invalid_for_loop", {"items": (1, 2)})

    @setup({"invalid_for_loop": "{% for x from items %}{{ x }}{% endfor %}"})
    def test_invalid_in_keyword(self):
        """
        Tests that the template engine raises a TemplateSyntaxError when a 'for' loop is defined with an invalid 'from' keyword instead of the correct 'in' keyword.

        The test case verifies that the engine correctly identifies and reports the syntax error, providing a meaningful error message to help with debugging.

        Args:
            None

        Raises:
            TemplateSyntaxError: If the 'for' loop syntax is invalid.

        Returns:
            None
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
