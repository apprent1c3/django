from django.template import TemplateSyntaxError
from django.template.defaulttags import ForNode
from django.test import SimpleTestCase

from ..utils import setup


class ForTagTests(SimpleTestCase):
    libraries = {"custom": "template_tests.templatetags.custom"}

    @setup({"for-tag01": "{% for val in values %}{{ val }}{% endfor %}"})
    def test_for_tag01(self):
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
        Tests the forloop.counter variable in a for loop within a template.

        This test case checks if the forloop.counter variable is correctly incremented and displayed.
        It renders a template with a for loop that iterates over a list of values and checks if the output matches the expected string.

        The template uses the forloop.counter variable to print the current loop iteration number, 
        and the test asserts that the rendered output contains the expected sequence of iteration numbers.
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
        Tests the functionality of for-loop variables in a template.

        The function verifies that the 'first' attribute of the forloop object behaves as expected, 
        marking the first iteration of the loop. This is done by rendering a template that 
        outputs 'f' for the first item in the loop and 'x' for subsequent items.

        The test case uses a list of identical values to ensure the correctness of the 
        forloop variable, regardless of the actual values being iterated over.

        Expected output is 'fxx', indicating that the first item is correctly identified 
        as the first iteration, and subsequent items are handled as expected.
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
        """

        Tests the unpacking of tuple items in a for loop within a template tag.

        The function verifies that the template engine correctly renders a string
        by iterating over a sequence of tuples, unpacking each tuple into key and value,
        and concatenating the key-value pairs with a slash separator.

        This test case covers the basic functionality of for loop unpacking in template tags,
        ensuring that the engine can handle tuple items and produce the expected output.

        """
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

        Tests the for tag unpacking functionality in the templating engine.

        This test checks if the for loop can correctly unpack key-value pairs from a tuple 
        and render them as a string. The expected output is a string where each key-value 
        pair is separated by a forward slash.

        :raises AssertionError: If the rendered output does not match the expected output.

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
        """
        Tests the error handling of the 'for' tag when using invalid unpacking syntax.

        Verifies that a TemplateSyntaxError is raised when attempting to unpack a value with 
        consecutive commas, such as 'key,,value', within a 'for' loop.

        Args:
            None

        Raises:
            TemplateSyntaxError: With a message indicating that the 'for' tag received an invalid argument.

        Note:
            This test case ensures that the template engine correctly reports syntax errors 
            when using the 'for' tag with invalid unpacking syntax, providing informative error messages 
            to help with debugging and development.

        """
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
        """
        Tests the for loop unpacking with too many variable targets.

        This test checks if the template engine correctly raises a TemplateSyntaxError when
        the for loop is used with too many variables in the unpacking syntax.

        The test template uses the for loop with three variables (key, value, and an extra comma),
        which is invalid syntax, and verifies that the expected error message is raised.

        The error message should indicate that the 'for' tag received an invalid argument.

        """
        msg = "'for' tag received an invalid argument: for key,value, in items"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string(
                "for-tag-unpack08", {"items": (("one", 1), ("two", 2))}
            )

    @setup({"double-quote": '{% for "k" in items %}{{ "k" }}/{% endfor %}'})
    def test_unpack_double_quote(self):
        """

        Tests if the template engine raises a TemplateSyntaxError when a 'for' tag with double quotes is used improperly.

        The test verifies that the engine correctly handles invalid syntax in a 'for' tag 
        by checking if a specific error message is raised when using double quotes around 
        the loop variable.

        :raises: TemplateSyntaxError

        """
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
        """

        Tests the unpacking of multiple variables in a for loop within a template.

        This function renders a template string that uses a for loop to iterate over a list of tuples, 
        unpacking each tuple into three variables. The rendered output is then compared to an expected string.

        The test covers two scenarios: one where an invalid variable in the template is replaced with a string, 
        and one where it is not replaced.

        :param None
        :returns: None
        :raises AssertionError: If the rendered output does not match the expected string.

        """
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
        Tests the for tag with an empty alternative when the input list is not empty.

        Verifies that the for loop renders each item in the list without displaying the
        empty text alternative. The test case passes if the output string contains all
        items from the input list concatenated together, in the order they appear.

        The test input is a list of integers, and the expected output is a string
        representing the concatenation of these integers. The test fails if the output
        contains the empty text or if the items are not rendered correctly.

        This test ensures that the for tag behaves correctly when the input list is not
        empty, rendering each item and ignoring the empty text alternative.
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
        output = self.engine.render_to_string("for-tag-empty02", {"values": []})
        self.assertEqual(output, "values array empty")

    @setup(
        {
            "for-tag-empty03": "{% for val in values %}"
            "{{ val }}{% empty %}values array not found{% endfor %}"
        }
    )
    def test_for_tag_empty03(self):
        """
        Checks the behavior of the for template tag when the iterable is empty, verifying that the empty block is rendered correctly.
        """
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

        Test rendering of a for-loop tag with string unpacking.

        This test case verifies that the template engine correctly unpacks string tuples
        into separate variables within a for-loop, and that the resulting output matches
        the expected string format.

        The test data consists of a tuple of strings, which is unpacked into two variables
        x and y within the for-loop. The expected output is a string with the unpacked
        values formatted as 'x:y/' for each iteration.

        The test passes if the rendered output matches the expected string.

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
        Tests that for loop unpacking requires exactly two values to unpack.

        This test case ensures that a ValueError is raised when attempting to unpack a
        single value in a for loop that expects two variables. The error message
        should indicate that exactly two values are required for unpacking.

        udeauCardContentDetailHelper-calenthis an mw
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
        Tests that the template engine correctly raises a TemplateSyntaxError when a 'for' loop statement in a template is missing required arguments, ensuring that the loop syntax is correctly validated.
        """
        msg = "'for' statements should have at least four words: for x items"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("invalid_for_loop", {"items": (1, 2)})

    @setup({"invalid_for_loop": "{% for x from items %}{{ x }}{% endfor %}"})
    def test_invalid_in_keyword(self):
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
