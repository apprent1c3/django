from django.forms import Widget
from django.forms.widgets import Input

from .base import WidgetTest


class WidgetTests(WidgetTest):
    def test_format_value(self):
        """
        Tests the format_value method of the Widget class, verifying it correctly handles None, empty string, and various data type inputs by returning the expected formatted values or None if input is empty or None.
        """
        widget = Widget()
        self.assertIsNone(widget.format_value(None))
        self.assertIsNone(widget.format_value(""))
        self.assertEqual(widget.format_value("español"), "español")
        self.assertEqual(widget.format_value(42.5), "42.5")

    def test_value_omitted_from_data(self):
        widget = Widget()
        self.assertIs(widget.value_omitted_from_data({}, {}, "field"), True)
        self.assertIs(
            widget.value_omitted_from_data({"field": "value"}, {}, "field"), False
        )

    def test_no_trailing_newline_in_attrs(self):
        self.check_html(
            Input(),
            "name",
            "value",
            strict=True,
            html='<input type="None" name="name" value="value">',
        )

    def test_attr_false_not_rendered(self):
        html = '<input type="None" name="name" value="value">'
        self.check_html(Input(), "name", "value", html=html, attrs={"readonly": False})
