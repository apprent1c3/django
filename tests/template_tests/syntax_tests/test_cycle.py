from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class CycleTagTests(SimpleTestCase):
    @setup({"cycle01": "{% cycle a %}"})
    def test_cycle01(self):
        """
        Tests that attempting to use an undefined named cycle in a template raises a TemplateSyntaxError.

        Checks that when a cycle is referenced in a template without being defined, the expected error message is raised, indicating that the named cycle is not defined.

        Args:
            None

        Raises:
            TemplateSyntaxError: With a message indicating that the named cycle 'a' is not defined.

        This test case covers the scenario where a template contains a cycle tag that references a non-existent named cycle, ensuring that the template engine correctly handles this situation and provides a meaningful error message.
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
        """
        Tests that a TemplateSyntaxError is raised when a cycle statement contains multiple syntax elements.

         The test checks that a specific error message is displayed when the template engine attempts to parse a cycle statement with multiple elements, 
         such as 'a,b,c', where only one element is expected to be defined as the cycle variable name.

         :raises: TemplateSyntaxError if the cycle statement contains multiple syntax elements.

        """
        msg = "Could not parse the remainder: ',b,c' from 'a,b,c'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("cycle07")

    @setup({"cycle10": "{% cycle 'a' 'b' 'c' as abc %}{% cycle abc %}"})
    def test_cycle10(self):
        output = self.engine.render_to_string("cycle10")
        self.assertEqual(output, "ab")

    @setup({"cycle11": "{% cycle 'a' 'b' 'c' as abc %}{% cycle abc %}{% cycle abc %}"})
    def test_cycle11(self):
        """

        Test the rendering of a template containing multiple nested cycle tags.

        This test case checks if the cycle function correctly repeats the defined cycle 
        when nested, and if the rendered output matches the expected result.

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
        """

        Tests the cycle function used within a for loop to alternate values in a template string.

        The cycle function is expected to switch between 'a' and 'b' after each iteration, prefixing each item in the test list with the current value in the cycle.

        The test passes if the rendered string matches the expected output, demonstrating the correct functionality of the cycle function within a loop.

        """
        output = self.engine.render_to_string("cycle13", {"test": list(range(5))})
        self.assertEqual(output, "a0,b1,a2,b3,a4,")

    @setup({"cycle14": "{% cycle one two as foo %}{% cycle foo %}"})
    def test_cycle14(self):
        output = self.engine.render_to_string("cycle14", {"one": "1", "two": "2"})
        self.assertEqual(output, "12")

    @setup({"cycle15": "{% for i in test %}{% cycle aye bee %}{{ i }},{% endfor %}"})
    def test_cycle15(self):
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
        output = self.engine.render_to_string("cycle17")
        self.assertEqual(output, "")

    @setup({"cycle18": "{% cycle 'a' 'b' 'c' as foo invalid_flag %}"})
    def test_cycle18(self):
        """
        Tests that the cycle template tag in a template raises a TemplateSyntaxError when used with an invalid flag, ensuring that only the 'silent' flag is allowed after the cycle's name.
        """
        msg = "Only 'silent' flag is allowed after cycle's name, not 'invalid_flag'."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("cycle18")

    @setup({"cycle19": "{% cycle 'a' 'b' as silent %}{% cycle silent %}"})
    def test_cycle19(self):
        """
        Tests the rendering of the Django template cycle tag when used within another cycle tag.

         Verifies that the inner cycle tag uses the silent variable from the outer cycle tag correctly, 
         resulting in the expected output 'ab' when the template is rendered to a string.
        """
        output = self.engine.render_to_string("cycle19")
        self.assertEqual(output, "ab")

    @setup({"cycle20": "{% cycle one two as foo %} &amp; {% cycle foo %}"})
    def test_cycle20(self):
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

        Tests the functionality of the cycle tag within a for loop in the templating engine.

        The cycle tag is expected to iterate over the provided values and assign a value 
        from the cycle ('a', 'b', 'c') to each iteration in a repeating pattern.

        The test case checks that the output of the rendered template matches the expected 
        result, where the cycle tag correctly assigns 'a', 'b', 'c' to each item in the list 
        and then restarts the cycle after reaching the end.

        The test verifies that the output is rendered as expected, with each item in the 
        input list having the correct character from the cycle prepended to it.

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
        """
        Tests the behavior of the cycle template tag when using a variable as an argument and when nesting cycle tags. 
        Verifies that the output of the nested cycle tags is rendered correctly and that HTML special characters are properly escaped.
        """
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

        Tests the rendering of a template that utilizes nested cycle tags.

        The function verifies that the Django template engine correctly handles a nested 
        cycle tag within an autoescape block, ensuring proper HTML character escaping 
        and correct rendering of the cycle pattern.

        It confirms that the output of the template is as expected, with the rendered 
        string containing the correctly escaped and cycled characters.

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
        Raises a TemplateSyntaxError when attempting to use a named cycle that has not been defined, ensuring proper error handling for undefined cycles in templating operations.
        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "Named cycle 'undefined' does not exist"
        ):
            self.engine.render_to_string("undefined_cycle")
