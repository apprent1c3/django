from django.forms.widgets import Input

from .base import WidgetTest


class InputTests(WidgetTest):
    def test_attrs_with_type(self):
        """

        Tests the construction of HTML input elements with specific attribute types.

        Verifies that the Input widget correctly renders 'date' and 'number' type attributes.

        """
        attrs = {"type": "date"}
        widget = Input(attrs)
        self.check_html(
            widget, "name", "value", '<input type="date" name="name" value="value">'
        )
        # reuse the same attrs for another widget
        self.check_html(
            Input(attrs),
            "name",
            "value",
            '<input type="date" name="name" value="value">',
        )
        attrs["type"] = "number"  # shouldn't change the widget type
        self.check_html(
            widget, "name", "value", '<input type="date" name="name" value="value">'
        )
