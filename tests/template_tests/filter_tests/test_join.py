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
        output = self.engine.render_to_string("join02", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha, beta & me")

    @setup({"join03": '{{ a|join:" &amp; " }}'})
    def test_join03(self):
        output = self.engine.render_to_string("join03", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha &amp; beta &amp; me")

    @setup({"join04": '{% autoescape off %}{{ a|join:" &amp; " }}{% endautoescape %}'})
    def test_join04(self):
        output = self.engine.render_to_string("join04", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha &amp; beta & me")

    # Joining with unsafe joiners doesn't result in unsafe strings.
    @setup({"join05": "{{ a|join:var }}"})
    def test_join05(self):
        """
        .\"\"\"
        Tests the join filter functionality in template rendering.

        The join filter is used to concatenate a list of strings with a specified separator.
        This test case verifies that the join filter correctly escapes special characters in the input strings, 
        ensuring the output is safe for HTML rendering.

        Args:
            a (list): A list of strings to be joined.
            var (str): The separator to use for joining the strings.

        Returns:
            str: The rendered template string with the joined and escaped input strings.

        """
        output = self.engine.render_to_string(
            "join05", {"a": ["alpha", "beta & me"], "var": " & "}
        )
        self.assertEqual(output, "alpha &amp; beta &amp; me")

    @setup({"join06": "{{ a|join:var }}"})
    def test_join06(self):
        output = self.engine.render_to_string(
            "join06", {"a": ["alpha", "beta & me"], "var": mark_safe(" & ")}
        )
        self.assertEqual(output, "alpha & beta &amp; me")

    @setup({"join07": "{{ a|join:var|lower }}"})
    def test_join07(self):
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

        Tests the join filter with autoescape turned off.

        This test ensures that when the autoescape is disabled, the join filter correctly 
        joins a list of strings with a specified joiner without escaping any HTML 
        characters in the strings.

        The test uses a list of strings containing HTML tags and special characters, 
        and verifies that the output matches the expected result, demonstrating that 
        the autoescape is indeed turned off during the join operation.

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
        Tests the behavior of the join function when a non-iterable argument is provided.

        The function verifies that when the join function is called with an object that cannot be iterated over, 
        it returns the original object unchanged, without raising any errors or attempting to modify the object.

        This test ensures that the join function handles such edge cases correctly and provides a predictable result.

        """
        obj = object()
        self.assertEqual(join(obj, "<br>"), obj)

    def test_noniterable_arg_autoescape_off(self):
        """
        Test that the join function returns the original non-iterable argument when autoescape is disabled.

            This test case verifies that when a non-iterable object is passed to the join function with autoescape set to False,
            the function returns the original object without attempting to iterate over it or apply any escaping.

        """
        obj = object()
        self.assertEqual(join(obj, "<br>", autoescape=False), obj)
