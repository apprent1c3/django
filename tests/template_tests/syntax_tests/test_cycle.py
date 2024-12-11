from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class CycleTagTests(SimpleTestCase):
    @setup({"cycle01": "{% cycle a %}"})
    def test_cycle01(self):
        """

        Tests that an error is raised when a named cycle is used in a template without being defined.

        Checks that the correct error message is generated when the template engine encounters an undefined cycle, 
        ensuring that the template syntax validation works correctly for cycle tags.

        """
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
        Tests the correct rendering of a Django template that utilizes the cycle template tag to iterate over a sequence of values, ensuring that the output matches the expected result when two cycles are nested, with the inner cycle referencing the outer cycle's name as a variable.
        """
        output = self.engine.render_to_string("cycle10")
        self.assertEqual(output, "ab")

    @setup({"cycle11": "{% cycle 'a' 'b' 'c' as abc %}{% cycle abc %}{% cycle abc %}"})
    def test_cycle11(self):
        """
        Tests the rendering of a Django template that utilizes the cycle tag to iterate over a sequence of values, ensuring the output matches the expected string 'abc' after multiple iterations.
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
        output = self.engine.render_to_string("cycle12")
        self.assertEqual(output, "abca")

    @setup({"cycle13": "{% for i in test %}{% cycle 'a' 'b' %}{{ i }},{% endfor %}"})
    def test_cycle13(self):
        output = self.engine.render_to_string("cycle13", {"test": list(range(5))})
        self.assertEqual(output, "a0,b1,a2,b3,a4,")

    @setup({"cycle14": "{% cycle one two as foo %}{% cycle foo %}"})
    def test_cycle14(self):
        output = self.engine.render_to_string("cycle14", {"one": "1", "two": "2"})
        self.assertEqual(output, "12")

    @setup({"cycle15": "{% for i in test %}{% cycle aye bee %}{{ i }},{% endfor %}"})
    def test_cycle15(self):
        """

        Tests the cycle function with two arguments, checking if it correctly alternates between the given values.

        This test case verifies the behavior of the cycle function when used within a loop, ensuring it produces the expected output 
        by cycling between 'aye' and 'bee' for each item in the 'test' list.

        """
        output = self.engine.render_to_string(
            "cycle15", {"test": list(range(5)), "aye": "a", "bee": "b"}
        )
        self.assertEqual(output, "a0,b1,a2,b3,a4,")

    @setup({"cycle16": "{% cycle one|lower two as foo %}{% cycle foo %}"})
    def test_cycle16(self):
        output = self.engine.render_to_string("cycle16", {"one": "A", "two": "2"})
        self.assertEqual(output, "a2")

    @setup(
        {
            "cycle17": "{% cycle 'a' 'b' 'c' as abc silent %}"
            "{% cycle abc %}{% cycle abc %}{% cycle abc %}{% cycle abc %}"
        }
    )
    def test_cycle17(self):
        """
        Test the silent cycling functionality with multiple occurrences.

        This test checks that when the 'silent' keyword is applied to the 'cycle'
        tag, it prevents the cycling variable from being rendered, even when
        the cycle is repeated multiple times.

        The expected result is an empty string, indicating that the cycling
        variable has not been output. 
        """
        output = self.engine.render_to_string("cycle17")
        self.assertEqual(output, "")

    @setup({"cycle18": "{% cycle 'a' 'b' 'c' as foo invalid_flag %}"})
    def test_cycle18(self):
        msg = "Only 'silent' flag is allowed after cycle's name, not 'invalid_flag'."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("cycle18")

    @setup({"cycle19": "{% cycle 'a' 'b' as silent %}{% cycle silent %}"})
    def test_cycle19(self):
        output = self.engine.render_to_string("cycle19")
        self.assertEqual(output, "ab")

    @setup({"cycle20": "{% cycle one two as foo %} &amp; {% cycle foo %}"})
    def test_cycle20(self):
        """
        Tests the cycle template tag to ensure it properly generates alternating values from a list and can be reused within the same template. 
        The test verifies that when a cycle is used to generate two alternating values, and then the same cycle is reused, the correct sequence of values is produced, including proper HTML escaping of ampersand characters.
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
        Tests the rendering of a template with a 'cycle' tag, specifically when the 'silent' option is used. 
         The function verifies that the 'cycle' tag, even when assigned a variable name, does not affect the rendered output when the 'silent' option is specified. 
         It checks if the engine correctly renders the input values without any influence from the 'cycle' tag, resulting in a simple concatenated string of the input values.
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
        """

        Tests the cycle function in the template engine.

        This test case checks if the cycle function correctly cycles over the given values ('a', 'b', 'c') 
        and appends the values from a list ('values') in the template.

        The expected output is a string where each value from the 'values' list is prepended with 
        a character from the cycle ('a', 'b', 'c'), repeating the cycle when necessary.

        """
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
        output = self.engine.render_to_string("cycle27", {"a": "<", "b": ">"})
        self.assertEqual(output, "<>")

    @setup({"cycle28": "{% cycle a|safe b as ab %}{% cycle ab %}"})
    def test_cycle28(self):
        """
        Tests the rendering of a template containing nested cycle tags, ensuring that HTML-safe strings are properly handled and escaped within the cycle. The test verifies that the output is correctly rendered, maintaining the original HTML characters.
        """
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
        Tests that using an undefined cycle in a Django template raises a TemplateSyntaxError.

        Raises a TemplateSyntaxError when attempting to render a template containing an undefined cycle, 
        verifying the error message indicates the cycle does not exist.

        The test evaluates the rendering process with a template containing a silent cycle definition 
        and a for loop attempting to use an undefined cycle, ensuring the correct error handling behavior.
        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "Named cycle 'undefined' does not exist"
        ):
            self.engine.render_to_string("undefined_cycle")
