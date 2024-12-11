import json

from django.template.loader import render_to_string
from django.test import SimpleTestCase


class TestTemplates(SimpleTestCase):
    def test_javascript_escaping(self):
        """

        Tests the proper escaping of JavaScript code in inline admin formsets.

        Verifies that HTML entities are correctly escaped and double quotes are properly 
        escaped within JavaScript strings, ensuring that inline admin formsets render 
        correctly in both stacked and tabular layouts.

        Checks for the presence of specific escaped strings in the rendered HTML output, 
        confirming that the template rendering process correctly handles special characters.

        """
        context = {
            "inline_admin_formset": {
                "inline_formset_data": json.dumps(
                    {
                        "formset": {"prefix": "my-prefix"},
                        "opts": {"verbose_name": "verbose name\\"},
                    }
                ),
            },
        }
        output = render_to_string("admin/edit_inline/stacked.html", context)
        self.assertIn("&quot;prefix&quot;: &quot;my-prefix&quot;", output)
        self.assertIn("&quot;verbose_name&quot;: &quot;verbose name\\\\&quot;", output)

        output = render_to_string("admin/edit_inline/tabular.html", context)
        self.assertIn("&quot;prefix&quot;: &quot;my-prefix&quot;", output)
        self.assertIn("&quot;verbose_name&quot;: &quot;verbose name\\\\&quot;", output)
