from django.contrib.auth.models import Group
from django.test import SimpleTestCase, override_settings

from ..utils import setup


@override_settings(DEBUG=True)
class DebugTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    @setup({"non_debug": "{% debug %}"})
    def test_non_debug(self):
        """

        Tests that the debug template tag is not rendered when the DEBUG setting is False.

        This test case verifies that the {% debug %} template tag does not produce any output
        when the application is running with DEBUG mode disabled, ensuring that sensitive
        information is not inadvertently exposed in a production environment.

        """
        output = self.engine.render_to_string("non_debug", {})
        self.assertEqual(output, "")

    @setup({"modules": "{% debug %}"})
    def test_modules(self):
        """

        Tests the rendering of the modules template.

        This test case verifies that the template contains the expected module information.
        It renders the 'modules' template and checks if the output includes the 'django' module.
        The test passes if the 'django' module is found in the rendered template output.

        """
        output = self.engine.render_to_string("modules", {})
        self.assertIn(
            "&#x27;django&#x27;: &lt;module &#x27;django&#x27; ",
            output,
        )

    @setup({"plain": "{% debug %}"})
    def test_plain(self):
        output = self.engine.render_to_string("plain", {"a": 1})
        self.assertTrue(
            output.startswith(
                "{&#x27;a&#x27;: 1}"
                "{&#x27;False&#x27;: False, &#x27;None&#x27;: None, "
                "&#x27;True&#x27;: True}\n\n{"
            )
        )

    @setup({"non_ascii": "{% debug %}"})
    def test_non_ascii(self):
        """
        Tests the rendering of non-ASCII characters in a template.

        This test case verifies that the template engine correctly handles non-ASCII characters when rendering a template. It creates a Group object with a non-ASCII name and passes it to the template for rendering. The test asserts that the output starts with the expected string representation of the Group object, ensuring that the non-ASCII characters are correctly encoded and displayed.
        """
        group = Group(name="清風")
        output = self.engine.render_to_string("non_ascii", {"group": group})
        self.assertTrue(output.startswith("{&#x27;group&#x27;: &lt;Group: 清風&gt;}"))

    @setup({"script": "{% debug %}"})
    def test_script(self):
        output = self.engine.render_to_string("script", {"frag": "<script>"})
        self.assertTrue(
            output.startswith("{&#x27;frag&#x27;: &#x27;&lt;script&gt;&#x27;}")
        )
