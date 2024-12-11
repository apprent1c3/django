from datetime import date

from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class RegroupTagTests(SimpleTestCase):
    @setup(
        {
            "regroup01": ""
            "{% regroup data by bar as grouped %}"
            "{% for group in grouped %}"
            "{{ group.grouper }}:"
            "{% for item in group.list %}"
            "{{ item.foo }}"
            "{% endfor %},"
            "{% endfor %}"
        }
    )
    def test_regroup01(self):
        """
        Tests the 'regroup' functionality in template rendering.

        The 'regroup' functionality allows data to be grouped by a common attribute.
        This test ensures that a list of items can be successfully grouped by the 'bar' attribute,
        and then iterated over to produce a string output. The expected output is a comma-separated string
        where each group is represented by its grouper value followed by a colon and the values of the 'foo' attribute
        of each item in the group, separated by commas.

        The test data consists of a list of dictionaries with 'foo' and 'bar' keys, and the test checks
        that the rendered output matches the expected string after grouping and iteration.

        """
        output = self.engine.render_to_string(
            "regroup01",
            {
                "data": [
                    {"foo": "c", "bar": 1},
                    {"foo": "d", "bar": 1},
                    {"foo": "a", "bar": 2},
                    {"foo": "b", "bar": 2},
                    {"foo": "x", "bar": 3},
                ],
            },
        )
        self.assertEqual(output, "1:cd,2:ab,3:x,")

    @setup(
        {
            "regroup02": ""
            "{% regroup data by bar as grouped %}"
            "{% for group in grouped %}"
            "{{ group.grouper }}:"
            "{% for item in group.list %}"
            "{{ item.foo }}"
            "{% endfor %}"
            "{% endfor %}"
        }
    )
    def test_regroup02(self):
        """
        Test for silent failure when target variable isn't found
        """
        output = self.engine.render_to_string("regroup02", {})
        self.assertEqual(output, "")

    @setup(
        {
            "regroup03": ""
            '{% regroup data by at|date:"m" as grouped %}'
            "{% for group in grouped %}"
            "{{ group.grouper }}:"
            "{% for item in group.list %}"
            '{{ item.at|date:"d" }}'
            "{% endfor %},"
            "{% endfor %}"
        }
    )
    def test_regroup03(self):
        """
        Regression tests for #17675
        The date template filter has expects_localtime = True
        """
        output = self.engine.render_to_string(
            "regroup03",
            {
                "data": [
                    {"at": date(2012, 2, 14)},
                    {"at": date(2012, 2, 28)},
                    {"at": date(2012, 7, 4)},
                ],
            },
        )
        self.assertEqual(output, "02:1428,07:04,")

    @setup(
        {
            "regroup04": ""
            '{% regroup data by bar|join:"" as grouped %}'
            "{% for group in grouped %}"
            "{{ group.grouper }}:"
            "{% for item in group.list %}"
            "{{ item.foo|first }}"
            "{% endfor %},"
            "{% endfor %}"
        }
    )
    def test_regroup04(self):
        """
        The join template filter has needs_autoescape = True
        """
        output = self.engine.render_to_string(
            "regroup04",
            {
                "data": [
                    {"foo": "x", "bar": ["ab", "c"]},
                    {"foo": "y", "bar": ["a", "bc"]},
                    {"foo": "z", "bar": ["a", "d"]},
                ],
            },
        )
        self.assertEqual(output, "abc:xy,ad:z,")

    # Test syntax errors
    @setup({"regroup05": "{% regroup data by bar as %}"})
    def test_regroup05(self):
        """
        Tests that a TemplateSyntaxError is raised when using the regroup template tag 
        without specifying the variable to regroup the data into. 

        This test case verifies that the template engine correctly handles invalid 
        template syntax by raising an exception when the 'as' keyword is missing 
        in the regroup template tag.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("regroup05")

    @setup({"regroup06": "{% regroup data by bar thisaintright grouped %}"})
    def test_regroup06(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("regroup06")

    @setup({"regroup07": "{% regroup data thisaintright bar as grouped %}"})
    def test_regroup07(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("regroup07")

    @setup({"regroup08": "{% regroup data by bar as grouped toomanyargs %}"})
    def test_regroup08(self):
        """

        Tests that the regroup template tag raises a TemplateSyntaxError when given too many arguments.

        The test case verifies that the template engine correctly handles an invalid regroup tag by
        raising an exception. Specifically, it checks that the error is triggered when more than the
        expected number of arguments are provided to the regroup tag.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("regroup08")

    @setup(
        {
            "regroup_unpack": "{% regroup data by bar as grouped %}"
            "{% for grouper, group in grouped %}"
            "{{ grouper }}:"
            "{% for item in group %}"
            "{{ item.foo }}"
            "{% endfor %},"
            "{% endfor %}"
        }
    )
    def test_regroup_unpack(self):
        output = self.engine.render_to_string(
            "regroup_unpack",
            {
                "data": [
                    {"foo": "c", "bar": 1},
                    {"foo": "d", "bar": 1},
                    {"foo": "a", "bar": 2},
                    {"foo": "b", "bar": 2},
                    {"foo": "x", "bar": 3},
                ],
            },
        )
        self.assertEqual(output, "1:cd,2:ab,3:x,")
