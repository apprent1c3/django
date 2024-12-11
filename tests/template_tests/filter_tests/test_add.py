from datetime import date, timedelta

from django.template.defaultfilters import add
from django.test import SimpleTestCase
from django.utils.translation import gettext_lazy

from ..utils import setup


class AddTests(SimpleTestCase):
    """
    Tests for #11687 and #16676
    """

    @setup({"add01": '{{ i|add:"5" }}'})
    def test_add01(self):
        output = self.engine.render_to_string("add01", {"i": 2000})
        self.assertEqual(output, "2005")

    @setup({"add02": '{{ i|add:"napis" }}'})
    def test_add02(self):
        output = self.engine.render_to_string("add02", {"i": 2000})
        self.assertEqual(output, "")

    @setup({"add03": "{{ i|add:16 }}"})
    def test_add03(self):
        """
        Tests the rendering of a template that attempts to add a non-integer value to an integer.
        The function checks that an empty string is returned when the 'add' filter is applied to a non-numeric input value, ensuring that the filter handles type mismatches correctly and does not raise any errors.
        """
        output = self.engine.render_to_string("add03", {"i": "not_an_int"})
        self.assertEqual(output, "")

    @setup({"add04": '{{ i|add:"16" }}'})
    def test_add04(self):
        """

        Tests the behavior of the add filter when the input is not an integer.

        This test case verifies that the add filter appends the specified value to the input,
        even if the input cannot be converted to an integer. The expected result is a string
        concatenation of the original input and the value to be added.

         организм 

        """
        output = self.engine.render_to_string("add04", {"i": "not_an_int"})
        self.assertEqual(output, "not_an_int16")

    @setup({"add05": "{{ l1|add:l2 }}"})
    def test_add05(self):
        """

        Tests the add filter functionality in the templating engine.

        The add filter is used to concatenate two lists into a single list.
        This test case checks if the filter correctly combines the input lists
        and produces the expected output, ensuring that the resulting list
        contains all elements from both input lists.

        The test input consists of two lists, each containing a set of numbers.
        The expected output is a single list with all numbers from both input lists.

        """
        output = self.engine.render_to_string("add05", {"l1": [1, 2], "l2": [3, 4]})
        self.assertEqual(output, "[1, 2, 3, 4]")

    @setup({"add06": "{{ t1|add:t2 }}"})
    def test_add06(self):
        output = self.engine.render_to_string("add06", {"t1": (3, 4), "t2": (1, 2)})
        self.assertEqual(output, "(3, 4, 1, 2)")

    @setup({"add07": "{{ d|add:t }}"})
    def test_add07(self):
        """
        Tests the 'add' filter template tag with a date and a timedelta object.

        The test verifies that adding a 10-day timedelta to January 1, 2000 results in the correct output, January 11, 2000.

        This test case ensures the date calculation functionality is correctly implemented in the template engine.
        """
        output = self.engine.render_to_string(
            "add07", {"d": date(2000, 1, 1), "t": timedelta(10)}
        )
        self.assertEqual(output, "Jan. 11, 2000")

    @setup({"add08": "{{ s1|add:lazy_s2 }}"})
    def test_add08(self):
        """
        Add two string values together, one of which is lazily translated, and verify the result.

        This test checks that the add filter correctly concatenates a regular string (`s1`) with a lazily translated string (`lazy_s2`). The function `gettext_lazy` is used to create the lazy translation, which is then added to the regular string using the `add` filter. The test asserts that the resulting string is the concatenation of the two input strings.
        """
        output = self.engine.render_to_string(
            "add08",
            {"s1": "string", "lazy_s2": gettext_lazy("lazy")},
        )
        self.assertEqual(output, "stringlazy")

    @setup({"add09": "{{ lazy_s1|add:lazy_s2 }}"})
    def test_add09(self):
        output = self.engine.render_to_string(
            "add09",
            {"lazy_s1": gettext_lazy("string"), "lazy_s2": gettext_lazy("lazy")},
        )
        self.assertEqual(output, "stringlazy")


class FunctionTests(SimpleTestCase):
    def test_add(self):
        self.assertEqual(add("1", "2"), 3)
