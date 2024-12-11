from django.template.defaultfilters import join
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class JoinTests(SimpleTestCase):
    @setup({"join01": '{{ a|join:", " }}'})
    def test_join01(self):
        """
        Tests the join filter functionality in the templating engine.

        The join filter is used to concatenate elements of an iterable into a single string,
        with a specified separator. This test verifies that the filter correctly handles
        special characters, such as ampersands, and HTML-encodes the output as expected.

        :raises AssertionError: if the rendered output does not match the expected result
        """
        output = self.engine.render_to_string("join01", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha, beta &amp; me")

    @setup({"join02": '{% autoescape off %}{{ a|join:", " }}{% endautoescape %}'})
    def test_join02(self):
        """
        Test the functionality of the join filter with a list of strings containing special characters.

        This test ensures that the join filter correctly concatenates a list of strings into a single string, separated by a specified delimiter, and that it handles special characters correctly without applying any escaping.

        The expected output is a comma-separated string of the input list elements, with no modification or escaping of the special characters.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Notes
        -----
        This test is part of a larger suite of tests designed to validate the functionality of the template engine's filters and syntax.

        """
        output = self.engine.render_to_string("join02", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha, beta & me")

    @setup({"join03": '{{ a|join:" &amp; " }}'})
    def test_join03(self):
        output = self.engine.render_to_string("join03", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha &amp; beta &amp; me")

    @setup({"join04": '{% autoescape off %}{{ a|join:" &amp; " }}{% endautoescape %}'})
    def test_join04(self):
        """
        Tests the join filter with autoescaping disabled and an ampersand in the input list.

        Verifies that the join filter correctly concatenates the elements of the input list
        with the specified separator and that HTML special characters are properly escaped.
        The test case includes an ampersand in one of the list elements to ensure correct handling.
        The expected output is a string where the list elements are joined with the specified separator
        and any HTML special characters are replaced with their corresponding HTML entities.
        """
        output = self.engine.render_to_string("join04", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha &amp; beta & me")

    # Joining with unsafe joiners doesn't result in unsafe strings.
    @setup({"join05": "{{ a|join:var }}"})
    def test_join05(self):
        """
        Tests the join filter functionality in templating, ensuring that the join string is properly escaped for HTML when concatenating a list of values with a custom separator.
        """
        output = self.engine.render_to_string(
            "join05", {"a": ["alpha", "beta & me"], "var": " & "}
        )
        self.assertEqual(output, "alpha &amp; beta &amp; me")

    @setup({"join06": "{{ a|join:var }}"})
    def test_join06(self):
        """

        Tests the 'join' filter with a custom separator.

        This tests the functionality of joining a list of strings with a specified separator,
        ensuring proper HTML escaping of the separator.

        :returns: None

        """
        output = self.engine.render_to_string(
            "join06", {"a": ["alpha", "beta & me"], "var": mark_safe(" & ")}
        )
        self.assertEqual(output, "alpha & beta &amp; me")

    @setup({"join07": "{{ a|join:var|lower }}"})
    def test_join07(self):
        """

        Tests the joining of a list of strings with a custom separator, 
        applied in a case-insensitive manner.

        The function verifies that the join filter correctly concatenates 
        the elements of the input list using the specified separator, 
        while also ensuring that the output is in lowercase.

        It also checks that any special characters in the input strings 
        are properly escaped in the resulting output.

        """
        output = self.engine.render_to_string(
            "join07", {"a": ["Alpha", "Beta & me"], "var": " & "}
        )
        self.assertEqual(output, "alpha &amp; beta &amp; me")

    @setup({"join08": "{{ a|join:var|lower }}"})
    def test_join08(self):
        output = self.engine.render_to_string(
            "join08", {"a": ["Alpha", "Beta & me"], "var": mark_safe(" & ")}
        )
        self.assertEqual(output, "alpha & beta &amp; me")

    @setup(
        {
            "join_autoescape_off": (
                "{% autoescape off %}"
                "{{ var_list|join:var_joiner }}"
                "{% endautoescape %}"
            ),
        }
    )
    def test_join_autoescape_off(self):
        var_list = ["<p>Hello World!</p>", "beta & me", "<script>Hi!</script>"]
        context = {"var_list": var_list, "var_joiner": "<br/>"}
        output = self.engine.render_to_string("join_autoescape_off", context)
        expected_result = "<p>Hello World!</p><br/>beta & me<br/><script>Hi!</script>"
        self.assertEqual(output, expected_result)


class FunctionTests(SimpleTestCase):
    def test_list(self):
        self.assertEqual(join([0, 1, 2], "glue"), "0glue1glue2")

    def test_autoescape(self):
        self.assertEqual(
            join(["<a>", "<img>", "</a>"], "<br>"),
            "&lt;a&gt;&lt;br&gt;&lt;img&gt;&lt;br&gt;&lt;/a&gt;",
        )

    def test_autoescape_off(self):
        self.assertEqual(
            join(["<a>", "<img>", "</a>"], "<br>", autoescape=False),
            "<a><br><img><br></a>",
        )

    def test_noniterable_arg(self):
        """
        Tests the behavior of join function when a non-iterable object is passed as an argument.

         Verifies that attempting to join a non-iterable object with a separator results in the original object being returned unchanged.
        """
        obj = object()
        self.assertEqual(join(obj, "<br>"), obj)

    def test_noniterable_arg_autoescape_off(self):
        """
        Tests that the join function handles a non-iterable argument correctly when autoescape is disabled.

        Verifies that when a single object is passed to the join function with autoescape set to False, the function returns the original object without modification, rather than attempting to concatenate or modify it.

        This ensures that the function behaves as expected and does not raise an error when given a non-iterable input with autoescape disabled.
        """
        obj = object()
        self.assertEqual(join(obj, "<br>", autoescape=False), obj)
