import json

from django.template.loader import render_to_string
from django.test import SimpleTestCase


class TestTemplates(SimpleTestCase):
    def test_javascript_escaping(self):
        """
        Checks if JavaScript strings are properly escaped in inline admin formset templates. Verifies that special characters in formset data are correctly replaced with their HTML entities to prevent JavaScript errors.
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
