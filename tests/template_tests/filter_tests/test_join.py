from django.template.defaultfilters import join
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class JoinTests(SimpleTestCase):
    @setup({"join01": '{{ a|join:", " }}'})
    def test_join01(self):
        output = self.engine.render_to_string("join01", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha, beta &amp; me")

    @setup({"join02": '{% autoescape off %}{{ a|join:", " }}{% endautoescape %}'})
    def test_join02(self):
        """
        ..:param self: Test class instance
            :return: None
            Tests the 'join' filter functionality when using an autoescape directive.
            The test renders a template with the 'join' filter applied to a list of strings, 
            including one containing an ampersand (&) character, and asserts the output is 
            correct with the ampersand remaining unescaped.
        """
        output = self.engine.render_to_string("join02", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha, beta & me")

    @setup({"join03": '{{ a|join:" &amp; " }}'})
    def test_join03(self):
        """
        Tests the join filter functionality in string rendering.

        Checks if the join filter correctly concatenates a list of strings into a single string with a specified separator.
        In this case, the separator is ' &amp; ', ensuring proper HTML escaping of any special characters in the input strings.

        The expected output is a string where all elements of the input list are joined with the specified separator, with any special characters properly escaped for HTML rendering.

        :raises AssertionError: If the rendered output does not match the expected string.

        """
        output = self.engine.render_to_string("join03", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha &amp; beta &amp; me")

    @setup({"join04": '{% autoescape off %}{{ a|join:" &amp; " }}{% endautoescape %}'})
    def test_join04(self):
        """
        Tests the join filter with autoescaping disabled, ensuring that HTML special characters are not escaped after the join operation, but only those that are not part of the joined value itself.
        """
        output = self.engine.render_to_string("join04", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha &amp; beta & me")

    # Joining with unsafe joiners doesn't result in unsafe strings.
    @setup({"join05": "{{ a|join:var }}"})
    def test_join05(self):
        """
        Tests the join filter functionality in template rendering.

        The function verifies that the join filter correctly concatenates a list of strings with a specified separator, 
        and that the output is properly escaped to prevent HTML injection attacks.

        It checks that the '&' character in the input list is correctly escaped to '&amp;' in the output string.

        This ensures that the join filter behaves as expected and produces safe output for web applications.
        """
        output = self.engine.render_to_string(
            "join05", {"a": ["alpha", "beta & me"], "var": " & "}
        )
        self.assertEqual(output, "alpha &amp; beta &amp; me")

    @setup({"join06": "{{ a|join:var }}"})
    def test_join06(self):
        """
        Test the join filter functionality when joining a list with a custom separator.

        This function evaluates the rendering of a template that uses the join filter to concatenate 
        a list of strings with a specified separator. The test case covers the handling of special 
        characters in the separator, ensuring they are properly escaped in the output HTML.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the rendered output does not match the expected result.
        """
        output = self.engine.render_to_string(
            "join06", {"a": ["alpha", "beta & me"], "var": mark_safe(" & ")}
        )
        self.assertEqual(output, "alpha & beta &amp; me")

    @setup({"join07": "{{ a|join:var|lower }}"})
    def test_join07(self):
        """
        Join a list of strings with a custom separator and render the result as a string.

        The function tests the rendering of a template that joins a list of strings using a specified separator. 
        It verifies that the join operation is performed correctly, including any necessary HTML escaping of special characters in the input strings.
        The result is a lowercase string with the specified separator between the joined elements.
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
        """

        Tests the functionality of joining a list of variables with an autoescape off directive.

        This test case verifies that the join filter works as expected when autoescaping is disabled.
        It checks if the joined string is rendered correctly without any HTML escaping, 
        using a list of variables containing HTML tags and special characters.

        The test renders a template with the joined variables and compares the output with the expected result.

        """
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
        Test that join function handles non-iterable argument by checking if it returns the original object when a non-iterable object is passed to it.
        """
        obj = object()
        self.assertEqual(join(obj, "<br>"), obj)

    def test_noniterable_arg_autoescape_off(self):
        """

        Tests that the join function handles non-iterable arguments correctly when autoescape is disabled.

        The function should return the original non-iterable argument unchanged, as there are no elements to join.

        Parameters are not checked in this test description. See function implementation for details.

        This test helps ensure the join function behaves as expected with different inputs and configuration settings, maintaining the stability and reliability of the application.

        """
        obj = object()
        self.assertEqual(join(obj, "<br>", autoescape=False), obj)
