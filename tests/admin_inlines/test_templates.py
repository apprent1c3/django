import json

from django.template.loader import render_to_string
from django.test import SimpleTestCase


class TestTemplates(SimpleTestCase):
    def test_javascript_escaping(self):
        """

        Tests that JavaScript data contained within the inline admin formset template context is properly escaped.

        Checks that JSON data, specifically the 'prefix' and 'verbose_name' fields, is rendered correctly in both stacked and tabular inline formset templates.

        Verifies that double quotes and backslashes within the data are correctly escaped to prevent JavaScript errors.

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
