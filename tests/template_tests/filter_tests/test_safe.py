from django.test import SimpleTestCase

from ..utils import setup


class SafeTests(SimpleTestCase):
    @setup({"safe01": "{{ a }} -- {{ a|safe }}"})
    def test_safe01(self):
        """

        Tests the safe filter functionality in templating engine.

        The test verifies that the templating engine correctly escapes and unescapes HTML entities
        when the safe filter is applied. This ensures that template variables can be safely rendered
        without introducing potential security vulnerabilities due to unescaped user input.

        :param None:
        :returns: None
        :raises: AssertionError if the rendered output does not match the expected result.

        """
        output = self.engine.render_to_string("safe01", {"a": "<b>hello</b>"})
        self.assertEqual(output, "&lt;b&gt;hello&lt;/b&gt; -- <b>hello</b>")

    @setup({"safe02": "{% autoescape off %}{{ a }} -- {{ a|safe }}{% endautoescape %}"})
    def test_safe02(self):
        output = self.engine.render_to_string("safe02", {"a": "<b>hello</b>"})
        self.assertEqual(output, "<b>hello</b> -- <b>hello</b>")
