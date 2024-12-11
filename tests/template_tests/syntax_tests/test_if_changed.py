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
        """

        Tests the ifchanged template tag functionality.

        This test case evaluates the rendering of a template that utilizes the ifchanged tag.
        The ifchanged tag is used to check if a value has changed since the last iteration in a loop.
        In this specific test, it checks the output of a template that iterates over a tuple of numbers (1, 1, 3) and only outputs the changed numbers.

        The expected output of this test is '13', indicating that the first number '1' is output,
        no change is detected for the second '1', and '3' is output as it is different from the previous value.

        """
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
        Tests the ifchanged template tag to verify that it correctly removes duplicates from a sequence of numbers. The test case checks that when a list of identical numbers is passed to the template, only the first occurrence of the number is rendered in the output.
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
        Tests the ifchanged template tag with nested for loops.

        This function checks the rendering of a template that uses multiple ifchanged tags
        within nested for loops. The test data includes lists of identical numbers to verify
        that the ifchanged tag correctly handles these scenarios and only outputs the
        first occurrence of each unique value.

        The expected output is compared to the actual rendered string to confirm the
        correct functioning of the ifchanged tag in this specific context.
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

        Tests the ifchanged template tag with multiple for loops and variables as parameters.

        Checks if the ifchanged tag correctly detects changes in the 'num' variable 
        and renders the expected '..' string whenever a change occurs, 
        while iterating over both 'num' and 'numx' variables.

        The test case verifies the output of the template rendering against the expected string '..567..567..567', 
        ensuring the ifchanged tag behaves as expected in a nested loop scenario.

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

        This test case verifies that the ifchanged tag correctly alternates between two values
        when the input is unchanged, and switches to a new value when the input changes.
        The test also checks that the else clause is executed when the input remains the same.

        The test input is a list of IDs with repeating values, and the expected output is a comma-separated string
        where each ID is followed by a color that changes when the ID changes, and remains the same color (gray) when the ID remains the same.

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

        Tests the ifchanged-else syntax in the templating engine.

        This test case verifies that the ifchanged-else statement correctly 
        alternates between two values when the input data changes, and 
        appends nothing when the data remains the same. The test checks 
        if the engine accurately handles a list of repeated and distinct 
        values, producing a string with the expected output pattern.

        Args:
            None

        Returns:
            None

        Checks:
            The output string against the expected pattern.

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
        """

        Tests the ifchanged template tag with an else clause.

        Checks that the template engine correctly renders a list of items, 
        changing the output when the value changes, and displaying a default 
        message when the value remains the same.

        The test verifies that the template correctly handles a sequence of 
        repeated and unique values, ensuring that the ifchanged tag behaves 
        as expected.

        """
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
        """
        Sets up the test class by initializing the engine and calling the superclass's setup method.

        This class method is invoked before any tests in the class are executed and is responsible for preparing the necessary resources.
        It creates an instance of the Engine class and assigns it to the class attribute, making it available for use in subsequent tests.
        The superclass's setup method is also called to ensure that any additional setup required by the parent class is performed.
        This method is typically used in test cases where the engine needs to be initialized once for all tests in the class.
        """
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
