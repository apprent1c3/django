from django.template import Context, Engine
from django.test import SimpleTestCase

from ..utils import setup


class IfChangedTagTests(SimpleTestCase):
    libraries = {"custom": "template_tests.templatetags.custom"}

    @setup(
        {
            "ifchanged01": (
                "{% for n in num %}{% ifchanged %}{{ n }}{% endifchanged %}{% endfor %}"
            )
        }
    )
    def test_ifchanged01(self):
        """
        Tester for ifchanged template tag behavior with numeric range.

        This function checks the functionality of the ifchanged template tag when provided with a range of numbers.
        It verifies that the tag correctly outputs only the changed values in the sequence, resulting in a concatenated string of unique consecutive numbers.
        The test passes if the rendered output matches the expected result of '123'.
        """
        output = self.engine.render_to_string("ifchanged01", {"num": (1, 2, 3)})
        self.assertEqual(output, "123")

    @setup(
        {
            "ifchanged02": (
                "{% for n in num %}{% ifchanged %}{{ n }}{% endifchanged %}{% endfor %}"
            )
        }
    )
    def test_ifchanged02(self):
        output = self.engine.render_to_string("ifchanged02", {"num": (1, 1, 3)})
        self.assertEqual(output, "13")

    @setup(
        {
            "ifchanged03": (
                "{% for n in num %}{% ifchanged %}{{ n }}{% endifchanged %}{% endfor %}"
            )
        }
    )
    def test_ifchanged03(self):
        """

        Tests the functionality of the ifchanged template tag with identical values.

        This test case evaluates the rendering of the ifchanged tag when all values in an iterable are the same.
        It verifies that the tag correctly outputs the value only once, even if the iterable contains duplicate values.

        The expected outcome is that the rendered output contains only the first occurrence of the value.

        """
        output = self.engine.render_to_string("ifchanged03", {"num": (1, 1, 1)})
        self.assertEqual(output, "1")

    @setup(
        {
            "ifchanged04": "{% for n in num %}{% ifchanged %}{{ n }}{% endifchanged %}"
            "{% for x in numx %}{% ifchanged %}{{ x }}{% endifchanged %}"
            "{% endfor %}{% endfor %}"
        }
    )
    def test_ifchanged04(self):
        """

        Tests the ifchanged template tag in a nested loop structure.

        Checks if the ifchanged tag correctly outputs the first occurrence of a repeated value 
        in both inner and outer loops. The function verifies that unchanged values are skipped 
        and only the first occurrence of each value in a sequence is rendered.

        """
        output = self.engine.render_to_string(
            "ifchanged04", {"num": (1, 2, 3), "numx": (2, 2, 2)}
        )
        self.assertEqual(output, "122232")

    @setup(
        {
            "ifchanged05": "{% for n in num %}{% ifchanged %}{{ n }}{% endifchanged %}"
            "{% for x in numx %}{% ifchanged %}{{ x }}{% endifchanged %}"
            "{% endfor %}{% endfor %}"
        }
    )
    def test_ifchanged05(self):
        """

        Tests the ifchanged template tag functionality with nested loops.

        The test verifies that the ifchanged tag correctly detects changes in the looped 
        variables and outputs the expected string. It specifically checks the behavior 
        when the ifchanged tag is used within nested for loops, ensuring that the tag 
        respects the scope of each loop and outputs the correct values.

        """
        output = self.engine.render_to_string(
            "ifchanged05", {"num": (1, 1, 1), "numx": (1, 2, 3)}
        )
        self.assertEqual(output, "1123123123")

    @setup(
        {
            "ifchanged06": "{% for n in num %}{% ifchanged %}{{ n }}{% endifchanged %}"
            "{% for x in numx %}{% ifchanged %}{{ x }}{% endifchanged %}"
            "{% endfor %}{% endfor %}"
        }
    )
    def test_ifchanged06(self):
        output = self.engine.render_to_string(
            "ifchanged06", {"num": (1, 1, 1), "numx": (2, 2, 2)}
        )
        self.assertEqual(output, "1222")

    @setup(
        {
            "ifchanged07": "{% for n in num %}{% ifchanged %}{{ n }}{% endifchanged %}"
            "{% for x in numx %}{% ifchanged %}{{ x }}{% endifchanged %}"
            "{% for y in numy %}{% ifchanged %}{{ y }}{% endifchanged %}"
            "{% endfor %}{% endfor %}{% endfor %}"
        }
    )
    def test_ifchanged07(self):
        """

        Tests the ifchanged template tag with nested loops.

        This function checks if the ifchanged tag correctly outputs values when used 
        in multiple nested for loops. The test case involves rendering a template with 
        three separate loops, each containing identical values. The ifchanged tag is 
        expected to only output each unique value once, resulting in the correct 
        output string.

        The test verifies the functionality by comparing the rendered output with the 
        expected string. It ensures that the ifchanged tag works as intended, even 
        when used in a nested loop structure.

        """
        output = self.engine.render_to_string(
            "ifchanged07", {"num": (1, 1, 1), "numx": (2, 2, 2), "numy": (3, 3, 3)}
        )
        self.assertEqual(output, "1233323332333")

    @setup(
        {
            "ifchanged08": "{% for data in datalist %}{% for c,d in data %}"
            "{% if c %}{% ifchanged %}{{ d }}{% endifchanged %}"
            "{% endif %}{% endfor %}{% endfor %}"
        }
    )
    def test_ifchanged08(self):
        """

        Tests the ifchanged template tag with multiple nested loops and conditional statements.

        The function verifies that the ifchanged tag correctly outputs a string by comparing the rendered template with the expected result.
        It checks if the tag only outputs the changed values and ignores the unchanged ones, while also respecting the inner conditional statements.
        The test covers scenarios where the inner loop values are filtered based on a condition and the ifchanged tag is applied to the filtered output.

        """
        output = self.engine.render_to_string(
            "ifchanged08",
            {
                "datalist": [
                    [(1, "a"), (1, "a"), (0, "b"), (1, "c")],
                    [(0, "a"), (1, "c"), (1, "d"), (1, "d"), (0, "e")],
                ]
            },
        )
        self.assertEqual(output, "accd")

    @setup(
        {
            "ifchanged-param01": (
                "{% for n in num %}{% ifchanged n %}..{% endifchanged %}"
                "{{ n }}{% endfor %}"
            )
        }
    )
    def test_ifchanged_param01(self):
        """
        Test one parameter given to ifchanged.
        """
        output = self.engine.render_to_string("ifchanged-param01", {"num": (1, 2, 3)})
        self.assertEqual(output, "..1..2..3")

    @setup(
        {
            "ifchanged-param02": (
                "{% for n in num %}{% for x in numx %}"
                "{% ifchanged n %}..{% endifchanged %}{{ x }}"
                "{% endfor %}{% endfor %}"
            )
        }
    )
    def test_ifchanged_param02(self):
        """

        Tests the 'ifchanged' parameter functionality in the templating engine.

        This test case evaluates the rendering of a template with nested loops and 
        an ifchanged condition. It verifies that the 'ifchanged' directive correctly 
        identifies changes in the outer loop variable 'n' and outputs the expected string.

        The test scenario involves two sets of numbers, 'num' and 'numx', which are 
        used as input data for the template. The expected output is a string 
        demonstrating the correct application of the 'ifchanged' directive.

        """
        output = self.engine.render_to_string(
            "ifchanged-param02", {"num": (1, 2, 3), "numx": (5, 6, 7)}
        )
        self.assertEqual(output, "..567..567..567")

    @setup(
        {
            "ifchanged-param03": "{% for n in num %}{{ n }}{% for x in numx %}"
            "{% ifchanged x n %}{{ x }}{% endifchanged %}"
            "{% endfor %}{% endfor %}"
        }
    )
    def test_ifchanged_param03(self):
        """
        Test multiple parameters to ifchanged.
        """
        output = self.engine.render_to_string(
            "ifchanged-param03", {"num": (1, 1, 2), "numx": (5, 6, 6)}
        )
        self.assertEqual(output, "156156256")

    @setup(
        {
            "ifchanged-param04": (
                "{% for d in days %}{% ifchanged %}{{ d.day }}{% endifchanged %}"
                "{% for h in d.hours %}{% ifchanged d h %}{{ h }}{% endifchanged %}"
                "{% endfor %}{% endfor %}"
            )
        }
    )
    def test_ifchanged_param04(self):
        """
        Test a date+hour like construct, where the hour of the last day is
        the same but the date had changed, so print the hour anyway.
        """
        output = self.engine.render_to_string(
            "ifchanged-param04",
            {"days": [{"hours": [1, 2, 3], "day": 1}, {"hours": [3], "day": 2}]},
        )
        self.assertEqual(output, "112323")

    @setup(
        {
            "ifchanged-param05": (
                "{% for d in days %}{% ifchanged d.day %}{{ d.day }}{% endifchanged %}"
                "{% for h in d.hours %}{% ifchanged d.day h %}{{ h }}{% endifchanged %}"
                "{% endfor %}{% endfor %}"
            )
        }
    )
    def test_ifchanged_param05(self):
        """
        Logically the same as above, just written with explicit ifchanged
        for the day.
        """
        output = self.engine.render_to_string(
            "ifchanged-param05",
            {"days": [{"hours": [1, 2, 3], "day": 1}, {"hours": [3], "day": 2}]},
        )
        self.assertEqual(output, "112323")

    @setup(
        {
            "ifchanged-else01": "{% for id in ids %}{{ id }}"
            "{% ifchanged id %}-first{% else %}-other{% endifchanged %}"
            ",{% endfor %}"
        }
    )
    def test_ifchanged_else01(self):
        """
        Test the else clause of ifchanged.
        """
        output = self.engine.render_to_string(
            "ifchanged-else01", {"ids": [1, 1, 2, 2, 2, 3]}
        )
        self.assertEqual(output, "1-first,1-other,2-first,2-other,2-other,3-first,")

    @setup(
        {
            "ifchanged-else02": "{% for id in ids %}{{ id }}-"
            '{% ifchanged id %}{% cycle "red" "blue" %}{% else %}gray{% endifchanged %}'
            ",{% endfor %}"
        }
    )
    def test_ifchanged_else02(self):
        """
        Tests the ifchanged template tag with an else clause.

        This test case checks the rendering of a template string that iterates over a list of IDs.
        For each ID, it applies the ifchanged tag to alternate between different colors (\"red\" and \"blue\") when the ID changes,
        and defaults to \"gray\" when the ID remains the same.
        The expected output is a comma-separated string of IDs with their corresponding colors.
        This test verifies the correct application of the ifchanged tag with an else clause in a templating engine.
        """
        output = self.engine.render_to_string(
            "ifchanged-else02", {"ids": [1, 1, 2, 2, 2, 3]}
        )
        self.assertEqual(output, "1-red,1-gray,2-blue,2-gray,2-gray,3-red,")

    @setup(
        {
            "ifchanged-else03": "{% for id in ids %}{{ id }}"
            '{% ifchanged id %}-{% cycle "red" "blue" %}{% else %}{% endifchanged %}'
            ",{% endfor %}"
        }
    )
    def test_ifchanged_else03(self):
        """

        Tests the ifchanged template tag with an else clause, specifically when the input list contains duplicate values.

        The test case verifies that the ifchanged tag correctly changes the output when the value of the loop variable changes, and also renders the else clause when the value remains the same. The test uses a template that cycles through colors ('red' and 'blue') to differentiate between changed and unchanged values.

        The expected output is a string containing the rendered list with changed values marked with a color, and unchanged values rendered without the color marker.

        """
        output = self.engine.render_to_string(
            "ifchanged-else03", {"ids": [1, 1, 2, 2, 2, 3]}
        )
        self.assertEqual(output, "1-red,1,2-blue,2,2,3-red,")

    @setup(
        {
            "ifchanged-else04": "{% for id in ids %}"
            "{% ifchanged %}***{{ id }}*{% else %}...{% endifchanged %}"
            "{{ forloop.counter }}{% endfor %}"
        }
    )
    def test_ifchanged_else04(self):
        output = self.engine.render_to_string(
            "ifchanged-else04", {"ids": [1, 1, 2, 2, 2, 3, 4]}
        )
        self.assertEqual(output, "***1*1...2***2*3...4...5***3*6***4*7")

    @setup(
        {
            "ifchanged-filter-ws": "{% load custom %}{% for n in num %}"
            '{% ifchanged n|noop:"x y" %}..{% endifchanged %}{{ n }}'
            "{% endfor %}"
        }
    )
    def test_ifchanged_filter_ws(self):
        """
        Test whitespace in filter arguments
        """
        output = self.engine.render_to_string("ifchanged-filter-ws", {"num": (1, 2, 3)})
        self.assertEqual(output, "..1..2..3")


class IfChangedTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine()
        super().setUpClass()

    def test_ifchanged_concurrency(self):
        """
        #15849 -- ifchanged should be thread-safe.
        """
        template = self.engine.from_string(
            "[0{% for x in foo %},{% with var=get_value %}{% ifchanged %}"
            "{{ var }}{% endifchanged %}{% endwith %}{% endfor %}]"
        )

        # Using generator to mimic concurrency.
        # The generator is not passed to the 'for' loop, because it does a list(values)
        # instead, call gen.next() in the template to control the generator.
        def gen():
            yield 1
            yield 2
            # Simulate that another thread is now rendering.
            # When the IfChangeNode stores state at 'self' it stays at '3' and
            # skip the last yielded value below.
            iter2 = iter([1, 2, 3])
            output2 = template.render(
                Context({"foo": range(3), "get_value": lambda: next(iter2)})
            )
            self.assertEqual(
                output2,
                "[0,1,2,3]",
                "Expected [0,1,2,3] in second parallel template, got {}".format(
                    output2
                ),
            )
            yield 3

        gen1 = gen()
        output1 = template.render(
            Context({"foo": range(3), "get_value": lambda: next(gen1)})
        )
        self.assertEqual(
            output1,
            "[0,1,2,3]",
            "Expected [0,1,2,3] in first template, got {}".format(output1),
        )

    def test_ifchanged_render_once(self):
        """
        #19890. The content of ifchanged template tag was rendered twice.
        """
        template = self.engine.from_string(
            '{% ifchanged %}{% cycle "1st time" "2nd time" %}{% endifchanged %}'
        )
        output = template.render(Context({}))
        self.assertEqual(output, "1st time")

    def test_include(self):
        """
        #23516 -- This works as a regression test only if the cached loader
        isn't used. Hence we don't use the @setup decorator.
        """
        engine = Engine(
            loaders=[
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "template": (
                            '{% for x in vars %}{% include "include" %}{% endfor %}'
                        ),
                        "include": "{% ifchanged %}{{ x }}{% endifchanged %}",
                    },
                ),
            ]
        )
        output = engine.render_to_string("template", {"vars": [1, 1, 2, 2, 3, 3]})
        self.assertEqual(output, "123")

    def test_include_state(self):
        """Tests the node state for different IncludeNodes (#27974)."""
        engine = Engine(
            loaders=[
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "template": (
                            '{% for x in vars %}{% include "include" %}'
                            '{% include "include" %}{% endfor %}'
                        ),
                        "include": "{% ifchanged %}{{ x }}{% endifchanged %}",
                    },
                ),
            ]
        )
        output = engine.render_to_string("template", {"vars": [1, 1, 2, 2, 3, 3]})
        self.assertEqual(output, "112233")
