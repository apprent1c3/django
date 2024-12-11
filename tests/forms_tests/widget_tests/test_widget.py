from django.forms import Widget
from django.forms.widgets import Input

from .base import WidgetTest


class WidgetTests(WidgetTest):
    def test_format_value(self):
        widget = Widget()
        self.assertIsNone(widget.format_value(None))
        self.assertIsNone(widget.format_value(""))
        self.assertEqual(widget.format_value("español"), "español")
        self.assertEqual(widget.format_value(42.5), "42.5")

    def test_value_omitted_from_data(self):
        """
        Check if a field's value is not present in the provided data.

        This method determines whether a specific field's value is missing or omitted 
        from the given data. It returns True if the value is not found and False otherwise.

        :param dict data: The dictionary containing the data to be checked.
        :param dict other_data: Another dictionary that may contain additional data.
        :param str field: The name of the field to check for in the data.

        :return: A boolean indicating whether the field's value is omitted from the data.
        """
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
        """

        Tests that an input field with a readonly attribute set to False is rendered correctly.

        The function verifies that the readonly attribute is not included in the HTML output when its value is False.

        :raises AssertionError: If the rendered HTML does not match the expected output.

        """
        html = '<input type="None" name="name" value="value">'
        self.check_html(Input(), "name", "value", html=html, attrs={"readonly": False})
