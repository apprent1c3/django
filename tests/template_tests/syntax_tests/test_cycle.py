from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class CycleTagTests(SimpleTestCase):
    @setup({"cycle01": "{% cycle a %}"})
    def test_cycle01(self):
        msg = "No named cycles in template. 'a' is not defined"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("cycle01")

    @setup({"cycle05": "{% cycle %}"})
    def test_cycle05(self):
        msg = "'cycle' tag requires at least two arguments"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("cycle05")

    @setup({"cycle07": "{% cycle a,b,c as foo %}{% cycle bar %}"})
    def test_cycle07(self):
        msg = "Could not parse the remainder: ',b,c' from 'a,b,c'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("cycle07")

    @setup({"cycle10": "{% cycle 'a' 'b' 'c' as abc %}{% cycle abc %}"})
    def test_cycle10(self):
        """
        Tests the cycle template tag with a nested cycle.

        Verifies that the cycle tag correctly iterates over a list of values and 
        renders the expected output when used within another cycle tag. 

        The test expects the output to be a string containing the first two 
        characters of the cycle, confirming that the nested cycle is properly 
        resolved and rendered.

        This test case ensures the cycle tag behaves as expected in complex 
        templating scenarios, providing a reliable way to generate repeating 
        patterns in templates.
        """
        output = self.engine.render_to_string("cycle10")
        self.assertEqual(output, "ab")

    @setup({"cycle11": "{% cycle 'a' 'b' 'c' as abc %}{% cycle abc %}{% cycle abc %}"})
    def test_cycle11(self):
        """
        Tests the 'cycle' template tag functionality in a template engine, specifically verifying that it correctly cycles through a list of values and renders the expected output when nested.
        """
        output = self.engine.render_to_string("cycle11")
        self.assertEqual(output, "abc")

    @setup(
        {
            "cycle12": (
                "{% cycle 'a' 'b' 'c' as abc %}{% cycle abc %}{% cycle abc %}"
                "{% cycle abc %}"
            )
        }
    )
    def test_cycle12(self):
        """

        Tests the cycle template tag with multiple invocations.

        The test verifies that the cycle tag can be used to iterate over a sequence of values 
        and that the output is rendered correctly when the cycle is referenced multiple times.

        The expected output is a string where each iteration of the cycle produces the next value 
        in the sequence, wrapping around to the start of the sequence when necessary.

        """
        output = self.engine.render_to_string("cycle12")
        self.assertEqual(output, "abca")

    @setup({"cycle13": "{% for i in test %}{% cycle 'a' 'b' %}{{ i }},{% endfor %}"})
    def test_cycle13(self):
        """
        Tests the functionality of the cycle tag when used within a for loop in a template.
        The cycle tag is used to cycle over a sequence of values, and this test ensures that the tag correctly alternates between the specified values ('a' and 'b') for each iteration of the loop.
        The test template renders a list of numbers from 0 to 4, prefixing each number with a value from the cycle ('a' or 'b').
        The expected output is a comma-separated string where each number is prefixed with the correct value from the cycle.
        """
        output = self.engine.render_to_string("cycle13", {"test": list(range(5))})
        self.assertEqual(output, "a0,b1,a2,b3,a4,")

    @setup({"cycle14": "{% cycle one two as foo %}{% cycle foo %}"})
    def test_cycle14(self):
        """
        Test the rendering of a template that utilizes nested cycle tags with a named variable, asserting the output results in an alternating pattern of the provided values.
        """
        output = self.engine.render_to_string("cycle14", {"one": "1", "two": "2"})
        self.assertEqual(output, "12")

    @setup({"cycle15": "{% for i in test %}{% cycle aye bee %}{{ i }},{% endfor %}"})
    def test_cycle15(self):
        """
        Tests the cycle function in templating engine.

        This test ensures that the cycle function correctly alternates between two values for each item in a list.

        It checks that the output is as expected, with the two values alternating in the correct order.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        AssertionError: If the output of the cycle function does not match the expected string.
        """
        output = self.engine.render_to_string(
            "cycle15", {"test": list(range(5)), "aye": "a", "bee": "b"}
        )
        self.assertEqual(output, "a0,b1,a2,b3,a4,")

    @setup({"cycle16": "{% cycle one|lower two as foo %}{% cycle foo %}"})
    def test_cycle16(self):
        """
        Tests the functionality of the cycle template tag with nested cycles and variable assignments.

        The test case verifies that the cycle tag correctly iterates over a list of values when a variable is assigned within the cycle and the variable is used in the subsequent cycle.

        It checks if the output of the rendered template matches the expected string 'a2' with the given input values 'A' and '2' for 'one' and 'two' respectively.
        """
        output = self.engine.render_to_string("cycle16", {"one": "A", "two": "2"})
        self.assertEqual(output, "a2")

    @setup(
        {
            "cycle17": "{% cycle 'a' 'b' 'c' as abc silent %}"
            "{% cycle abc %}{% cycle abc %}{% cycle abc %}{% cycle abc %}"
        }
    )
    def test_cycle17(self):
        output = self.engine.render_to_string("cycle17")
        self.assertEqual(output, "")

    @setup({"cycle18": "{% cycle 'a' 'b' 'c' as foo invalid_flag %}"})
    def test_cycle18(self):
        msg = "Only 'silent' flag is allowed after cycle's name, not 'invalid_flag'."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("cycle18")

    @setup({"cycle19": "{% cycle 'a' 'b' as silent %}{% cycle silent %}"})
    def test_cycle19(self):
        """

        Tests the functionality of the cycle template tag when used in conjunction with the 'as' keyword.

        This function verifies that the template engine correctly renders a template that contains 
        nested cycle tags, one of which is defined as a silent variable using the 'as' keyword.

        The expected output of the rendered template is a string consisting of the characters 'a' and 'b', 
        which are the values cycled through in the template. If the output matches this expectation, 
        the test is considered passed, confirming that the cycle and 'as' keywords are working as expected.

        """
        output = self.engine.render_to_string("cycle19")
        self.assertEqual(output, "ab")

    @setup({"cycle20": "{% cycle one two as foo %} &amp; {% cycle foo %}"})
    def test_cycle20(self):
        """
        Tests the cycle tag functionality when using a named variable to propagate values across multiple invocations. 
        The function verifies that the cycle tag correctly alternates between values, 
        and that the named variable can be used to repeat the cycle and produce the expected output string.
        """
        output = self.engine.render_to_string(
            "cycle20", {"two": "C & D", "one": "A & B"}
        )
        self.assertEqual(output, "A &amp; B &amp; C &amp; D")

    @setup(
        {
            "cycle21": "{% filter force_escape %}"
            "{% cycle one two as foo %} & {% cycle foo %}{% endfilter %}"
        }
    )
    def test_cycle21(self):
        """

        Tests the proper escaping of HTML entities in the cycle template tag.

        This test case verifies that the cycle tag correctly escapes special characters
        when used in conjunction with the force_escape filter. It ensures that ampersand
        characters in the input data are properly encoded as HTML entities in the output.

        The test verifies that the expected output matches the actual output of the template,
        checking for correct escaping of ampersand characters in both the original and cycled values.

        """
        output = self.engine.render_to_string(
            "cycle21", {"two": "C & D", "one": "A & B"}
        )
        self.assertEqual(output, "A &amp;amp; B &amp; C &amp;amp; D")

    @setup(
        {
            "cycle22": (
                "{% for x in values %}{% cycle 'a' 'b' 'c' as abc silent %}{{ x }}"
                "{% endfor %}"
            )
        }
    )
    def test_cycle22(self):
        """
        Tests the 'cycle' template tag with silent option to ensure it doesn't interfere with the output when not used.

        The test verifies that the template engine correctly renders a list of values when the 'cycle' tag is used with the silent option,
        but the cycled variable is not referenced in the template. The expected output is a concatenated string of the input values.

        This test case covers a scenario where the 'cycle' tag is used but its output is not utilized, ensuring that the engine behaves as expected
        in such situations and the result does not contain any characters from the cycle operation.
        """
        output = self.engine.render_to_string("cycle22", {"values": [1, 2, 3, 4]})
        self.assertEqual(output, "1234")

    @setup(
        {
            "cycle23": "{% for x in values %}"
            "{% cycle 'a' 'b' 'c' as abc silent %}{{ abc }}{{ x }}{% endfor %}"
        }
    )
    def test_cycle23(self):
        output = self.engine.render_to_string("cycle23", {"values": [1, 2, 3, 4]})
        self.assertEqual(output, "a1b2c3a4")

    @setup(
        {
            "cycle24": (
                "{% for x in values %}"
                "{% cycle 'a' 'b' 'c' as abc silent %}{% include 'included-cycle' %}"
                "{% endfor %}"
            ),
            "included-cycle": "{{ abc }}",
        }
    )
    def test_cycle24(self):
        """
        Test the cycle function in a templating engine.

        This function verifies that the cycle function correctly alternates between a set of values 
        ('a', 'b', 'c') in a loop. The test case includes a templating setup with a for loop 
        that iterates over a list of values, using the cycle function to alternate between 'a', 'b', 
        and 'c' and including a separate template 'included-cycle' in each iteration. 

        The expected output of this test is a string where the cycle function has correctly 
        alternated between 'a', 'b', and 'c' for the given number of iterations, resulting in the 
        string 'abca' for a list of four values.\"\"\"
        ```
        """
        output = self.engine.render_to_string("cycle24", {"values": [1, 2, 3, 4]})
        self.assertEqual(output, "abca")

    @setup({"cycle25": "{% cycle a as abc %}"})
    def test_cycle25(self):
        output = self.engine.render_to_string("cycle25", {"a": "<"})
        self.assertEqual(output, "&lt;")

    @setup({"cycle26": "{% cycle a b as ab %}{% cycle ab %}"})
    def test_cycle26(self):
        output = self.engine.render_to_string("cycle26", {"a": "<", "b": ">"})
        self.assertEqual(output, "&lt;&gt;")

    @setup(
        {
            "cycle27": (
                "{% autoescape off %}{% cycle a b as ab %}{% cycle ab %}"
                "{% endautoescape %}"
            )
        }
    )
    def test_cycle27(self):
        """
        Tests the cycle template tag within an autoescape block.

        This test case verifies that the cycle template tag properly alternates between values
        when used inside an autoescape off block and that the output is correctly escaped.

        The expected output is a string containing the characters '<' and '>' in the correct order,
        indicating successful rendering of the cycle template tag within the autoescape block.

        """
        output = self.engine.render_to_string("cycle27", {"a": "<", "b": ">"})
        self.assertEqual(output, "<>")

    @setup({"cycle28": "{% cycle a|safe b as ab %}{% cycle ab %}"})
    def test_cycle28(self):
        output = self.engine.render_to_string("cycle28", {"a": "<", "b": ">"})
        self.assertEqual(output, "<&gt;")

    @setup(
        {
            "cycle29": "{% cycle 'a' 'b' 'c' as cycler silent %}"
            "{% for x in values %}"
            "{% ifchanged x %}"
            "{% cycle cycler %}{{ cycler }}"
            "{% else %}"
            "{{ cycler }}"
            "{% endifchanged %}"
            "{% endfor %}"
        }
    )
    def test_cycle29(self):
        """
        A named {% cycle %} tag works inside an {% ifchanged %} block and a
        {% for %} loop.
        """
        output = self.engine.render_to_string(
            "cycle29", {"values": [1, 2, 3, 4, 5, 6, 7, 8, 8, 8, 9, 9]}
        )
        self.assertEqual(output, "bcabcabcccaa")

    @setup(
        {
            "cycle30": "{% cycle 'a' 'b' 'c' as cycler silent %}"
            "{% for x in values %}"
            "{% with doesnothing=irrelevant %}"
            "{% ifchanged x %}"
            "{% cycle cycler %}{{ cycler }}"
            "{% else %}"
            "{{ cycler }}"
            "{% endifchanged %}"
            "{% endwith %}"
            "{% endfor %}"
        }
    )
    def test_cycle30(self):
        """
        A {% with %} tag shouldn't reset the {% cycle %} variable.
        """
        output = self.engine.render_to_string(
            "cycle30", {"irrelevant": 1, "values": [1, 2, 3, 4, 5, 6, 7, 8, 8, 8, 9, 9]}
        )
        self.assertEqual(output, "bcabcabcccaa")

    @setup(
        {
            "undefined_cycle": "{% cycle 'a' 'b' 'c' as cycler silent %}"
            "{% for x in values %}"
            "{% cycle undefined %}{{ cycler }}"
            "{% endfor %}"
        }
    )
    def test_cycle_undefined(self):
        """
        Test that the templating engine correctly handles and raises an exception when attempting to cycle through a non-existent named cycle.

        :raises: TemplateSyntaxError
        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "Named cycle 'undefined' does not exist"
        ):
            self.engine.render_to_string("undefined_cycle")
